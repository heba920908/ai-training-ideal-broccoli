import asyncio

from commons.user_service.client import UserServiceClient
from commons.user_service.user_info import UserCreate, UserSearchRequest, UserUpdate
from fastmcp import FastMCP

mcp = FastMCP(name="users-management-mcp-server")
user_client = UserServiceClient()


@mcp.tool()
async def get_user_by_id(user_id: int) -> str:
    """Provides full user information by user_id"""
    return await asyncio.to_thread(user_client.get_user, user_id)


@mcp.tool()
async def delete_user(user_id: int) -> str:
    """Deletes user by user_id"""
    return await asyncio.to_thread(user_client.delete_user, user_id)


@mcp.tool()
async def search_user(search_user_request: UserSearchRequest) -> str:
    """Searches for users by name, surname, email and gender"""
    return await asyncio.to_thread(
        user_client.search_users, **search_user_request.model_dump()
    )


@mcp.tool()
async def add_user(user_create_model: UserCreate) -> str:
    """Adds new user into the system"""
    return await asyncio.to_thread(user_client.add_user, user_create_model)


@mcp.tool()
async def update_user(user_id: int, user_update_model: UserUpdate) -> str:
    """Updates user by user_id"""
    return await asyncio.to_thread(user_client.update_user, user_id, user_update_model)
