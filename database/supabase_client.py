
import os
from functools import lru_cache
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit.runtime.scriptrunner import get_script_run_ctx
from supabase import Client, create_client


# Locate the project root and load its .env file.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

def _get_config_value(name: str):
    """Read configuration from environment variables or Streamlit secrets."""

    value = os.getenv(name)

    if value:
        return value

    try:
        return st.secrets.get(name)
    except Exception:
        return None

def _create_regular_client() -> Client:
    """Create a Supabase client using the publishable/anon key."""

    supabase_url = _get_config_value("SUPABASE_URL")
    supabase_key = _get_config_value("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise EnvironmentError(
            "Missing SUPABASE_URL or SUPABASE_KEY in the .env file."
        )

    return create_client(supabase_url, supabase_key)


@lru_cache(maxsize=1)
def _get_standalone_client() -> Client:
    """
    Reuse a client for standalone scripts and backend tests.

    Streamlit users do not use this shared client.
    """

    return _create_regular_client()


def get_supabase_client() -> Client:
    """
    Retrieve the appropriate authenticated Supabase client.

    Streamlit:
        One client per browser session.

    Standalone scripts:
        One cached client for the running script.
    """

    context = get_script_run_ctx(suppress_warning=True)

    if context is not None:
        if "_supabase_client" not in st.session_state:
            st.session_state["_supabase_client"] = (
                _create_regular_client()
            )

        return st.session_state["_supabase_client"]

    return _get_standalone_client()


@lru_cache(maxsize=1)
def get_service_role_client() -> Client:
    """
    Create a trusted backend-only Supabase client.

    This client must never be exposed to the frontend.
    """

    supabase_url = _get_config_value("SUPABASE_URL")
    service_role_key = _get_config_value("SUPABASE_SERVICE_ROLE_KEY")

    if not supabase_url or not service_role_key:
        raise EnvironmentError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY "
            "in the .env file."
        )

    return create_client(
        supabase_url,
        service_role_key,
    )
