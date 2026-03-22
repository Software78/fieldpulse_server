from datetime import datetime


def detect_conflict(checklist_response, client_modified_at: datetime) -> bool:
    """
    Detect if there's a conflict between client and server data.
    
    Args:
        checklist_response: The existing ChecklistResponse object from server
        client_modified_at: The timestamp when client last had the data
        
    Returns:
        True if checklist_response.last_modified_at > client_modified_at
        (server was modified after the client's last known state)
    """
    if not checklist_response:
        return False
        
    if not client_modified_at:
        return False
        
    return checklist_response.last_modified_at > client_modified_at


def build_conflict_response(client_data, server_response) -> dict:
    """
    Build a conflict response payload with both client and server versions.
    
    Args:
        client_data: The data submitted by the client
        server_response: The existing ChecklistResponse object from server
        
    Returns:
        Dict with client_version and server_version containing data and timestamps
    """
    return {
        "client_version": {
            "data": client_data.get("data", {}),
            "client_modified_at": client_data.get("client_modified_at")
        },
        "server_version": {
            "data": server_response.data if server_response else {},
            "last_modified_at": server_response.last_modified_at if server_response else None
        }
    }
