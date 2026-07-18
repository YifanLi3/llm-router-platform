"""Phase 3 Streamlit dashboard for the LLM Router."""

from __future__ import annotations

import streamlit as st

from api import API_BASE_URL, DashboardApiError, fetch_json

st.set_page_config(
    page_title="LLM Router Console",
    page_icon="🧭",
    layout="wide",
)

st.title("🧭 LLM Router Console")
st.caption(f"Backend: `{API_BASE_URL}`")

def load_endpoint(path: str) -> dict | None:
    """Show an honest error instead of displaying fake dashboard data."""
    try:
        return fetch_json(path)
    except DashboardApiError as error:
        st.error(f"Data unavailable: {error}")
        return None

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Page", ["Overview", "Models", "Performance"])

    if st.button("Refresh data"):
        st.rerun()

    st.divider()
    status = load_endpoint("/status")

    if status is not None:
        if status["status"] == "healthy":
            st.success("System healthy")
        elif status["status"] == "degraded":
            st.warning("System degraded")
        else:
            st.error("System unhealthy")
        st.caption(f"Router mode: {status['router_mode']}")
        st.caption(f"Telemetry records: {status['telemetry_records']}")

if page == "Overview":
    st.header("Overview")
    analytics = load_endpoint("/analytics")
    health = load_endpoint("/health")
    if analytics is not None:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Requests", analytics["total_requests"])
        col2.metric("Avg latency", f"{analytics['average_latency_ms']:.1f} ms")
        col3.metric("Success rate", f"{analytics['success_rate']:.1%}")
        col4.metric("Total cost", f"${analytics['total_cost_usd']:.6f}")
        col5.metric("Cache hit rate", f"{analytics['cache_hit_rate']:.1%}")
        st.subheader("Requests by user tier")
        st.dataframe(
            analytics["user_tiers"],
            use_container_width=True,
            hide_index=True,
        )
    if health is not None:
        st.subheader("Provider health")
        provider_rows = []
        for provider_name, provider_info in health["services"]["inference"]["details"][
            "providers"
        ].items():
            provider_rows.append(
                {
                    "provider": provider_name,
                    "healthy": provider_info["healthy"],
                    "models": ", ".join(provider_info["models"]),
                    "reason": provider_info.get("reason", ""),
                }
            )
        st.dataframe(provider_rows, use_container_width=True, hide_index=True)
elif page == "Models":
    st.header("Models")
    analytics = load_endpoint("/analytics")
    if analytics is not None:
        models = analytics["models"]
        if not models:
            st.info("No model data yet. Send requests to POST /route first.")
        else:
            st.dataframe(models, use_container_width=True, hide_index=True)
            st.subheader("Requests by model")
            request_counts = {
                model["model_name"]: model["request_count"]
                for model in models
            }
            st.bar_chart(request_counts)
            st.subheader("Average latency by model")
            latency = {
                model["model_name"]: model["average_latency_ms"]
                for model in models
            }
            st.bar_chart(latency)
elif page == "Performance":
    st.header("Performance")
    quality = load_endpoint("/quality/dashboard")
    if quality is not None:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Requests", quality["request_count"])
        col2.metric("Avg latency", f"{quality['average_latency_ms']:.1f} ms")
        col3.metric("P95 latency", f"{quality['p95_latency_ms']:.1f} ms")
        col4.metric("Error rate", f"{quality['error_rate']:.1%}")
        st.subheader("Latency SLO")
        if quality["slo_latency_compliant"]:
            st.success("P95 latency is within the 1000 ms SLO.")
        else:
            st.error("P95 latency exceeds the 1000 ms SLO.")
        st.subheader("Hotspot models")
        if quality["hotspots"]:
            for model_name in quality["hotspots"]:
                st.warning(f"{model_name} exceeds the latency threshold.")
        else:
            st.success("No latency hotspots detected.")