"""
ERPNext Connection Helper for Docker Network Access.

Handles both internal Docker network and external access patterns.
"""

from frappeclient import FrappeClient
from typing import Optional


def connect_to_erpnext(
    url: str,
    api_key: str,
    api_secret: str,
    domain: Optional[str] = None
) -> FrappeClient:
    """
    Connect to ERPNext with proper configuration for your setup.
    
    For Docker network access (Jupyter + ERPNext same network):
        url = "http://erpnext-frontend:8080"
        domain = "well.rosslyn.cloud"  # Host header required
    
    For external access:
        url = "https://well.rosslyn.cloud"
        domain = None  # No Host header needed
    
    Args:
        url: ERPNext URL (internal Docker or external)
        api_key: API key from ERPNext
        api_secret: API secret from ERPNext
        domain: Domain for Host header (only for Docker network)
        
    Returns:
        Authenticated FrappeClient with proper headers
        
    Examples:
        >>> # Docker network (your current setup)
        >>> client = connect_to_erpnext(
        ...     url="http://erpnext-frontend:8080",
        ...     api_key="your_key",
        ...     api_secret="your_secret",
        ...     domain="well.rosslyn.cloud"
        ... )
        
        >>> # External access (fallback)
        >>> client = connect_to_erpnext(
        ...     url="https://well.rosslyn.cloud",
        ...     api_key="your_key",
        ...     api_secret="your_secret"
        ... )
    """
    # Create client
    client = FrappeClient(url)
    
    # Authenticate
    client.authenticate(api_key, api_secret)
    
    # Add Host header for Docker network routing if needed
    if domain:
        client.session.headers.update({"Host": domain})
        print(f"✓ Host header set: {domain}")
    
    return client


def test_connection(client: FrappeClient) -> bool:
    """
    Test ERPNext connection.
    
    Args:
        client: FrappeClient to test
        
    Returns:
        True if connection works
    """
    try:
        # Try to fetch customers
        customers = client.get_list(
            "Customer",
            fields=["name"],
            limit_page_length=1
        )
        
        print(f"✓ Connection successful")
        return True
        
    except Exception as e:
        print(f"✗ Connection test failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Check ERPNext is running: docker ps")
        print("  2. Verify API key and secret")
        print("  3. Try external URL: https://well.rosslyn.cloud")
        return False
