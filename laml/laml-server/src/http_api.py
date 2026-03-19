#!/usr/bin/env python3
"""HTTP API server for LAML dashboard.

This provides a REST API for the dashboard to fetch stats,
since the MCP server uses stdio transport.

Run with: python -m src.http_api
"""

import json
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from src.db.client import db
from src.db.backend_router import get_session_store, get_working_memory_store
from src.config import config
from src.metrics import metrics
from src.memory.backend import get_memory_repository

# Capture server start time and code file modification time for sync detection
_SERVER_START_TIME = datetime.now()
_CODE_FILE_PATH = os.path.abspath(__file__)
_CODE_MTIME = datetime.fromtimestamp(os.path.getmtime(_CODE_FILE_PATH))


def _is_local_endpoint(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(host in lowered for host in ("localhost", "127.0.0.1", "host.docker.internal"))


def _vector_deployment_location() -> str:
    backend = config.vector_backend
    if backend == "firebolt":
        return "local" if config.firebolt.use_core else "cloud"
    if backend == "elastic":
        return "local" if _is_local_endpoint(config.elastic.url) else "cloud"
    if backend == "clickhouse":
        host = config.clickhouse.host or ""
        return "local" if _is_local_endpoint(host) else "cloud"
    if backend == "turbopuffer":
        return "local" if _is_local_endpoint(config.turbopuffer.base_url) else "cloud"
    return "cloud"


class DashboardAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for dashboard API."""

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        try:
            if path == '/api/stats':
                self.handle_stats(query)
            elif path.startswith('/api/calls/'):
                service = path.split('/')[-1]
                self.handle_calls(service, query)
            elif path == '/api/vector-backend':
                self.handle_vector_backend(query)
            elif path == '/api/analytics':
                self.handle_analytics(query)
            elif path == '/api/config':
                self.handle_config()
            elif path == '/api/version':
                self.handle_version()
            elif path == '/api/health':
                self.send_json({"status": "ok"})
            else:
                self.send_json({"error": "Not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def handle_stats(self, query):
        """Get LAML stats."""
        time_window = int(query.get('window', [60])[0])

        # Get metrics from collector (local firebolt calls)
        service_stats = metrics.get_stats(time_window)

        # Augment with database metrics for ollama/embedding (cross-process) - Firebolt only
        try:
            if config.vector_backend == "firebolt":
                # Get ollama metrics from database - windowed stats
                ollama_window = db.execute(f"""
                SELECT
                    COUNT(*) as cnt,
                    COALESCE(AVG(latency_ms), 0) as avg_lat,
                    COALESCE(SUM(tokens_in), 0) as tok_in,
                    COALESCE(SUM(tokens_out), 0) as tok_out,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errs
                FROM service_metrics
                WHERE service = 'ollama'
                AND recorded_at > NOW() - INTERVAL '{time_window} minutes'
            """)

            # Get ollama TOTAL counts (all time, no window filter)
            ollama_totals = db.execute("""
                SELECT
                    COUNT(*) as total_cnt,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as total_errs
                FROM service_metrics
                WHERE service = 'ollama'
            """)

            total_ollama_calls = int(ollama_totals[0][0]) if ollama_totals else 0
            total_ollama_errors = int(ollama_totals[0][1]) if ollama_totals and ollama_totals[0][1] else 0

            if ollama_window and int(ollama_window[0][0]) > 0:
                service_stats["services"]["ollama"] = {
                    "calls_in_window": int(ollama_window[0][0]),
                    "avg_latency_ms": round(float(ollama_window[0][1]), 2),
                    "tokens_in_window": int(ollama_window[0][2]) if ollama_window[0][2] else 0,
                    "tokens_out_window": int(ollama_window[0][3]) if ollama_window[0][3] else 0,
                    "errors_in_window": int(ollama_window[0][4]) if ollama_window[0][4] else 0,
                    "total_calls": total_ollama_calls,
                    "total_errors": total_ollama_errors,
                }
            elif total_ollama_calls > 0:
                # No recent calls but we have historical data
                service_stats["services"]["ollama"] = {
                    "calls_in_window": 0,
                    "avg_latency_ms": 0,
                    "tokens_in_window": 0,
                    "tokens_out_window": 0,
                    "errors_in_window": 0,
                    "total_calls": total_ollama_calls,
                    "total_errors": total_ollama_errors,
                }

            # Get embedding metrics from database - windowed stats (Firebolt)
            embed_window = db.execute(f"""
                SELECT
                    COUNT(*) as cnt,
                    COALESCE(AVG(latency_ms), 0) as avg_lat,
                    COALESCE(SUM(tokens_in), 0) as tok_in,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errs
                FROM service_metrics
                WHERE service = 'embedding'
                AND recorded_at > NOW() - INTERVAL '{time_window} minutes'
            """)

            # Get embedding TOTAL counts (all time, no window filter)
            embed_totals = db.execute("""
                SELECT
                    COUNT(*) as total_cnt,
                    SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as total_errs
                FROM service_metrics
                WHERE service = 'embedding'
            """)

            total_embed_calls = int(embed_totals[0][0]) if embed_totals else 0
            total_embed_errors = int(embed_totals[0][1]) if embed_totals and embed_totals[0][1] else 0

            if embed_window and int(embed_window[0][0]) > 0:
                service_stats["services"]["embedding"] = {
                    "calls_in_window": int(embed_window[0][0]),
                    "avg_latency_ms": round(float(embed_window[0][1]), 2),
                    "tokens_in_window": int(embed_window[0][2]) if embed_window[0][2] else 0,
                    "errors_in_window": int(embed_window[0][3]) if embed_window[0][3] else 0,
                    "total_calls": total_embed_calls,
                    "total_errors": total_embed_errors,
                }
            elif total_embed_calls > 0:
                # No recent calls but we have historical data
                service_stats["services"]["embedding"] = {
                    "calls_in_window": 0,
                    "avg_latency_ms": 0,
                    "tokens_in_window": 0,
                    "errors_in_window": 0,
                    "total_calls": total_embed_calls,
                    "total_errors": total_embed_errors,
                }
        except Exception:
            pass

        # Always ensure all three service keys exist for dashboard (zeros if missing)
        for key in ("ollama", "embedding", "firebolt"):
            if key not in service_stats.get("services", {}):
                service_stats.setdefault("services", {})[key] = {
                    "calls_in_window": 0,
                    "errors_in_window": 0,
                    "avg_latency_ms": 0,
                    "p95_latency_ms": 0,
                    "total_calls": 0,
                    "total_errors": 0,
                }
                if key == "ollama":
                    service_stats["services"][key]["tokens_in_window"] = 0
                    service_stats["services"][key]["tokens_out_window"] = 0
                    service_stats["services"][key]["by_operation"] = {}
                elif key == "firebolt":
                    service_stats["services"][key]["by_operation"] = {}

        # Get memory counts (long-term from configured backend; sessions/wm from same backend via stores)
        try:
            repo = get_memory_repository()
            ltm_count = repo.count_total(include_deleted=False)

            session_store = get_session_store()
            wm_store = get_working_memory_store()
            session_count = session_store.count_all()
            wm_items = wm_store.count_all()
            wm_tokens = wm_store.sum_tokens_all()

            # access_log and storage_stats: Firebolt-only (same DB as service_metrics)
            access_log_count = 0
            by_category = {}
            top_accessed = []
            storage_stats = {
                "total_compressed": 0,
                "total_uncompressed": 0,
                "tables": {},
                "total_compressed_formatted": "0 B",
                "total_uncompressed_formatted": "0 B",
            }
            # Category breakdown and top accessed: use backend-agnostic repository helpers
            try:
                by_category = getattr(repo, "get_category_counts")()
            except Exception:
                by_category = {}
            try:
                raw_top = getattr(repo, "get_top_accessed")(limit=5)
                top_accessed = [
                    (
                        row["memory_id"],
                        row.get("memory_category") or row.get("category") or "",
                        row.get("access_count", 0),
                        row.get("importance", 0.0),
                        row.get("content", ""),
                    )
                    for row in raw_top
                ]
            except Exception:
                top_accessed = []

            if config.vector_backend == "firebolt":
                access_result = db.execute(
                    "SELECT COUNT(*) FROM memory_access_log"
                )
                access_log_count = access_result[0][0] if access_result else 0

            # Get storage sizes for the active backend.
            storage_stats = {"total_compressed": 0, "total_uncompressed": 0, "tables": {}}
            if config.vector_backend == "firebolt":
                try:
                    LAML_TABLES = [
                        "long_term_memories",
                        "working_memory_items",
                        "session_contexts",
                        "memory_access_log",
                        "memory_relationships",  # Join table for memory linking
                        "tool_error_log",        # Error tracking
                        "service_metrics",       # Ollama/embedding metrics (if exists)
                    ]
                    tables_result = db.execute("SHOW TABLES")
                    # SHOW TABLES columns (Firebolt Core):
                    # 0=table_name, 1=table_type, 2=column_count, 3=primary_index, 4=create_statement,
                    # 5=number_of_rows, 6=size_compressed, 7=size_uncompressed, 8=compression_ratio, 9=?
                    for row in tables_result:
                        table_name = row[0]
                        if table_name in LAML_TABLES:
                            row_count = int(row[5]) if row[5] else 0
                            compressed = row[6] if row[6] else "0 B"
                            uncompressed = row[7] if row[7] else "0 B"

                            # Parse size strings like "75.70 KiB" to bytes
                            def parse_size(size_str):
                                if not size_str or size_str == "0.00 B":
                                    return 0
                                parts = size_str.split()
                                if len(parts) != 2:
                                    return 0
                                value = float(parts[0])
                                unit = parts[1].upper()
                                multipliers = {"B": 1, "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}
                                return int(value * multipliers.get(unit, 1))

                            comp_bytes = parse_size(compressed)
                            uncomp_bytes = parse_size(uncompressed)

                            storage_stats["tables"][table_name] = {
                                "rows": row_count,
                                "compressed": compressed,
                                "compressed_bytes": comp_bytes,
                                "uncompressed": uncompressed,
                                "uncompressed_bytes": uncomp_bytes,
                            }
                            storage_stats["total_compressed"] += comp_bytes
                            storage_stats["total_uncompressed"] += uncomp_bytes
                except Exception as e:
                    storage_stats["error"] = str(e)
            elif config.vector_backend == "elastic":
                # Approximate storage size from Elasticsearch index stats
                try:
                    get_bytes = getattr(repo, "get_storage_bytes", None)
                    total_bytes = int(get_bytes()) if get_bytes is not None else 0
                    storage_stats["tables"]["elastic_long_term_memories"] = {
                        "rows": ltm_count,
                        "compressed": "",  # filled in after format_size
                        "compressed_bytes": total_bytes,
                        "uncompressed": "",
                        "uncompressed_bytes": total_bytes,
                    }
                    storage_stats["total_compressed"] = total_bytes
                    storage_stats["total_uncompressed"] = total_bytes
                except Exception as e:
                    storage_stats["error"] = str(e)
            elif config.vector_backend == "turbopuffer":
                # Approximate logical storage from Turbopuffer namespace metadata
                try:
                    get_bytes = getattr(repo, "get_storage_bytes", None)
                    total_bytes = int(get_bytes()) if get_bytes is not None else 0
                    storage_stats["tables"]["turbopuffer_namespaces"] = {
                        "rows": ltm_count + session_count + wm_items,
                        "compressed": "",
                        "compressed_bytes": total_bytes,
                        "uncompressed": "",
                        "uncompressed_bytes": total_bytes,
                    }
                    storage_stats["total_compressed"] = total_bytes
                    storage_stats["total_uncompressed"] = total_bytes
                except Exception as e:
                    storage_stats["error"] = str(e)
            else:
                # Other backends: explicitly mark metric as not available
                storage_stats["note"] = (
                    f"Storage size reporting is only implemented for Firebolt and Elasticsearch. "
                    f"Active backend: {config.vector_backend}."
                )

            # Format total sizes
            def format_size(bytes_val):
                if bytes_val < 1024:
                    return f"{bytes_val} B"
                elif bytes_val < 1024**2:
                    return f"{bytes_val/1024:.2f} KiB"
                elif bytes_val < 1024**3:
                    return f"{bytes_val/1024**2:.2f} MiB"
                else:
                    return f"{bytes_val/1024**3:.2f} GiB"

            storage_stats["total_compressed_formatted"] = format_size(storage_stats["total_compressed"])
            storage_stats["total_uncompressed_formatted"] = format_size(storage_stats["total_uncompressed"])

            memory_stats = {
                "long_term_memories": ltm_count,
                "active_sessions": session_count,
                "working_memory_items": wm_items,
                "working_memory_tokens": wm_tokens,
                "access_log_entries": access_log_count,
                "by_category": by_category,
                "top_accessed": [
                    {
                        "memory_id": row[0][:8] + "..." if row[0] else "",
                        "category": row[1],
                        "access_count": row[2],
                        "importance": row[3],
                        "content_preview": (row[4][:100] + "..." if len(row[4]) > 100 else row[4]) if row[4] else "",
                    }
                    for row in top_accessed
                ],
                "storage": storage_stats,
            }

            # For non-Firebolt vector backends, service_metrics table may be unavailable.
            # Backfill meaningful service counters from memory state so dashboard cards
            # don't misleadingly show zeros.
            if config.vector_backend == "turbopuffer":
                ollama_svc = service_stats["services"].get("ollama", {})
                if int(ollama_svc.get("total_calls", 0) or 0) == 0:
                    ollama_svc["total_calls"] = int(ltm_count)
                    ollama_svc["calls_in_window"] = int(ltm_count)
                    service_stats["services"]["ollama"] = ollama_svc

                embed_svc = service_stats["services"].get("embedding", {})
                if int(embed_svc.get("total_calls", 0) or 0) == 0:
                    embed_svc["total_calls"] = int(ltm_count)
                    embed_svc["calls_in_window"] = int(ltm_count)
                    service_stats["services"]["embedding"] = embed_svc
        except Exception as e:
            memory_stats = {
                "long_term_memories": 0,
                "active_sessions": 0,
                "working_memory_items": 0,
                "working_memory_tokens": 0,
                "access_log_entries": 0,
                "by_category": {},
                "top_accessed": [],
                "storage": {
                    "total_compressed": 0,
                    "total_uncompressed": 0,
                    "total_compressed_formatted": "0 B",
                    "total_uncompressed_formatted": "0 B",
                    "tables": {},
                },
                "error": str(e),
            }

        self.send_json({
            **service_stats,
            "memory": memory_stats,
        })

    def handle_calls(self, service, query):
        """Get recent calls for a service."""
        limit = int(query.get('limit', [50])[0])

        # First try to get from database (persisted across restarts)
        calls = []
        try:
            result = db.execute(f"""
                SELECT
                    recorded_at,
                    operation,
                    latency_ms,
                    tokens_in,
                    tokens_out,
                    success,
                    error_msg
                FROM service_metrics
                WHERE service = '{service}'
                ORDER BY recorded_at DESC
                LIMIT {limit}
            """)

            calls = [
                {
                    "timestamp": str(row[0]),
                    "operation": row[1],
                    "latency_ms": round(float(row[2]), 2),
                    "tokens_in": int(row[3]) if row[3] else 0,
                    "tokens_out": int(row[4]) if row[4] else 0,
                    "success": row[5] if isinstance(row[5], bool) else str(row[5]).lower() == 'true',
                    "error": row[6],
                }
                for row in result
            ]
        except Exception:
            # Fall back to in-memory metrics
            calls = metrics.get_recent_calls(service, limit)

        self.send_json({
            "service": service,
            "call_count": len(calls),
            "calls": calls,
        })

    def handle_config(self):
        """Get LAML configuration (vector backend, brain location, etc)."""
        payload = {
            "vector_backend": config.vector_backend,
            "dual_write_backend": config.dual_write_backend or None,
            "brain_location": _vector_deployment_location(),
            "firebolt": {
                "use_core": config.firebolt.use_core,
                "core_url": config.firebolt.core_url if config.firebolt.use_core else None,
                "account_name": config.firebolt.account_name if not config.firebolt.use_core else None,
                "database": config.firebolt.database,
            },
            "ollama": {
                "host": config.ollama.host,
                "model": config.ollama.model,
                "embedding_model": config.ollama.embedding_model,
            },
        }
        if config.vector_backend == "elastic":
            payload["elastic"] = {
                "url": config.elastic.url,
                "index_name": config.elastic.index_name,
            }
        if config.vector_backend == "clickhouse":
            payload["clickhouse"] = {
                "host": config.clickhouse.host,
                "port": config.clickhouse.port,
                "database": config.clickhouse.database,
                "table_name": config.clickhouse.table_name,
            }
        if config.vector_backend == "turbopuffer":
            payload["turbopuffer"] = {
                "region": config.turbopuffer.region,
                "base_url": config.turbopuffer.base_url,
                "long_term_namespace": config.turbopuffer.long_term_namespace,
                "sessions_namespace": config.turbopuffer.sessions_namespace,
                "working_memory_namespace": config.turbopuffer.working_memory_namespace,
            }
        self.send_json(payload)

    def handle_vector_backend(self, query):
        """
        Get or update the active vector backend.

        - GET /api/vector-backend          -> current backend + config
        - GET /api/vector-backend?backend=elastic|firebolt|clickhouse
          -> switch backend at runtime (and ensure basic target setup) then return updated config.
        """
        backend_vals = query.get("backend", [])
        if not backend_vals:
            # Just return current config
            self.handle_config()
            return

        new_backend = backend_vals[0].strip().lower()
        if new_backend not in ("firebolt", "elastic", "clickhouse", "turbopuffer"):
            self.send_json({"error": f"Invalid backend '{new_backend}'"}, 400)
            return

        # Best-effort setup for target backend (indexes/tables), without blocking on failures.
        try:
            if new_backend == "elastic":
                # Ensure ES index exists
                from scripts.init_elastic_index import main as init_elastic_index_main  # type: ignore

                init_elastic_index_main()
            elif new_backend == "clickhouse":
                # Ensure ClickHouse table exists
                from scripts.init_clickhouse import main as init_clickhouse_main  # type: ignore

                init_clickhouse_main()
            elif new_backend == "turbopuffer":
                # Turbopuffer namespaces are created lazily on first write.
                pass
            else:
                # Firebolt backend uses existing schema.sql and migrate.py; nothing to do here.
                pass
        except Exception as e:
            # Log but don't abort the switch; UI can surface the error if needed.
            print(f"[handle_vector_backend] setup for {new_backend} failed: {e}")

        # Update in-memory config so subsequent calls use the new backend.
        config.vector_backend = new_backend

        # Return updated config so the UI can immediately reflect the change.
        payload = {
            "vector_backend": config.vector_backend,
            "dual_write_backend": config.dual_write_backend or None,
            "brain_location": _vector_deployment_location(),
            "firebolt": {
                "use_core": config.firebolt.use_core,
                "core_url": config.firebolt.core_url if config.firebolt.use_core else None,
                "account_name": config.firebolt.account_name if not config.firebolt.use_core else None,
                "database": config.firebolt.database,
            },
            "ollama": {
                "host": config.ollama.host,
                "model": config.ollama.model,
                "embedding_model": config.ollama.embedding_model,
            },
        }
        if config.vector_backend == "elastic":
            payload["elastic"] = {
                "url": config.elastic.url,
                "index_name": config.elastic.index_name,
            }
        if config.vector_backend == "clickhouse":
            payload["clickhouse"] = {
                "host": config.clickhouse.host,
                "port": config.clickhouse.port,
                "database": config.clickhouse.database,
                "table_name": config.clickhouse.table_name,
            }
        if config.vector_backend == "turbopuffer":
            payload["turbopuffer"] = {
                "region": config.turbopuffer.region,
                "base_url": config.turbopuffer.base_url,
                "long_term_namespace": config.turbopuffer.long_term_namespace,
                "sessions_namespace": config.turbopuffer.sessions_namespace,
                "working_memory_namespace": config.turbopuffer.working_memory_namespace,
            }
        self.send_json(payload)

    def handle_version(self):
        """Get server version info and detect code sync issues.

        Returns server start time, code modification time, and whether
        the server needs a restart to pick up code changes.
        """
        # Re-check file mtime in case it changed
        current_mtime = datetime.fromtimestamp(os.path.getmtime(_CODE_FILE_PATH))

        # Server needs restart if code was modified after server started
        needs_restart = current_mtime > _SERVER_START_TIME

        self.send_json({
            "server_start_time": _SERVER_START_TIME.isoformat(),
            "code_modified_time": current_mtime.isoformat(),
            "code_loaded_time": _CODE_MTIME.isoformat(),
            "needs_restart": needs_restart,
            "uptime_seconds": (datetime.now() - _SERVER_START_TIME).total_seconds(),
            "message": "Server is running stale code - restart required!" if needs_restart else "Server is up to date",
        })

    def handle_analytics(self, query):
        """Get memory analytics (Firebolt backend only for category/importance breakdown)."""
        user_id = query.get('user_id', [None])[0]
        try:
            if config.vector_backend != "firebolt":
                self.send_json({
                    "by_subtype": [],
                    "by_importance": {},
                    "user_filter": user_id or "all",
                    "note": "Analytics breakdown available with Firebolt vector backend only.",
                })
                return

            user_filter = ""
            params = ()
            if user_id:
                user_filter = "AND user_id = ?"
                params = (user_id,)

            subtype_result = db.execute(f"""
                SELECT memory_category, memory_subtype, COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY memory_category, memory_subtype
                ORDER BY cnt DESC
            """, params)

            by_subtype = [
                {"category": row[0], "subtype": row[1], "count": row[2]}
                for row in subtype_result
            ]

            importance_result = db.execute(f"""
                SELECT
                    CASE
                        WHEN importance >= 0.8 THEN 'critical'
                        WHEN importance >= 0.6 THEN 'high'
                        WHEN importance >= 0.4 THEN 'medium'
                        ELSE 'low'
                    END as priority,
                    COUNT(*) as cnt
                FROM long_term_memories
                WHERE deleted_at IS NULL {user_filter}
                GROUP BY priority
            """, params)

            by_importance = {row[0]: row[1] for row in importance_result}

            self.send_json({
                "by_subtype": by_subtype,
                "by_importance": by_importance,
                "user_filter": user_id or "all",
            })
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_server(port=8082):
    """Run the HTTP API server."""
    server = HTTPServer(('', port), DashboardAPIHandler)
    print(f"🔥 FML Dashboard API running on http://localhost:{port}")
    print(f"   Endpoints:")
    print(f"   - GET /api/stats")
    print(f"   - GET /api/calls/<service>")
    print(f"   - GET /api/analytics")
    print(f"   - GET /api/health")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
