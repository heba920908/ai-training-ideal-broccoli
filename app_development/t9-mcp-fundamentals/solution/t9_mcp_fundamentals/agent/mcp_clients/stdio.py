from mcp import Client
from mcp.client.stdio import StdioServerParameters
from t9_mcp_fundamentals.agent.mcp_clients.base import MCPClient


class StdioMCPClient(MCPClient):
    """
    Handles MCP server connection and tool execution via stdio.

    Supports two launch modes:
    1. Podman image - pass docker_image="docker.io/mcp/duckduckgo:latest"
    2. Local script - pass command="python", args=["path/to/stdio_server.py"]

    In both cases the MCP protocol runs over the process's stdin/stdout.
    You do NOT need to start the process manually; the client spawns it for you.

    Usage examples:
        # Podman
        async with StdioMCPClient(docker_image="mcp/duckduckgo:latest") as client:
            ...

        # Local stdio server
        async with StdioMCPClient(command="python", args=["t9_mcp_fundamentals/mcp_server/stdio_server.py"]) as client:
            ...
    """

    def __init__(
        self,
        docker_image: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        container_runtime: str = "podman",
    ) -> None:
        """
        Args:
            docker_image: Container image name. By default the client runs
                          `podman run --rm -i <docker_image>` to launch the server.
            command:      Executable to run for a local stdio server (e.g. "python").
                          Ignored when docker_image is set.
            args:         Arguments for the local executable
                          (e.g. ["path/to/stdio_server.py"]).
            env:          Optional environment variables forwarded to the process.
        """
        if docker_image is None and command is None:
            raise ValueError(
                "Provide either 'docker_image' or 'command' to launch the MCP server."
            )

        super().__init__()
        self.docker_image = docker_image
        self.command = command
        self.args = args or []
        self.env = env
        self.container_runtime = container_runtime

    def _build_server_params(self) -> StdioServerParameters:
        if self.docker_image:
            return StdioServerParameters(
                command=self.container_runtime,
                args=["run", "--rm", "-i", self.docker_image],
                env=self.env,
            )
        return StdioServerParameters(command=self.command, args=self.args, env=self.env)

    def _startup_message(self) -> str:
        if self.docker_image:
            return (
                f"Starting {self.container_runtime} container: {self.docker_image}\n"
                f"To inspect running containers: {self.container_runtime} ps --filter 'ancestor={self.docker_image}'"
            )
        return f"Starting local stdio server: {self.command} {' '.join(self.args)}"

    async def __aenter__(self):
        print(self._startup_message())
        client = Client(self._build_server_params(), read_timeout_seconds=60)
        await client.__aenter__()
        self.client = client
        print(
            f"Connected to {client.server_info} (protocol version {client.protocol_version})"
        )
        print(
            f"Capabilities: {client.server_capabilities.model_dump_json(indent=2, exclude_none=True)}"
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            try:
                await self.client.__aexit__(exc_type, exc_val, exc_tb)
            finally:
                self.client = None
