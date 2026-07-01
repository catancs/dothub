import gzip
import io
import json
import re
import tarfile
from posixpath import normpath


class BundleError(ValueError):
    pass


SECRET_PATTERNS = [
    r"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{8,}",          # generic sk- (OpenAI-style)
    r"(?<![A-Za-z0-9])sk-ant-[A-Za-z0-9_\-]{8,}",   # Anthropic
    r"ghp_[A-Za-z0-9]{20,}",                        # GitHub personal access token
    r"gh[os]r?_[A-Za-z0-9]{20,}",                   # GitHub OAuth/server/refresh
    r"xox[bp]-[A-Za-z0-9-]{10,}",                   # Slack bot/user token
    r"AKIA[0-9A-Z]{16}",                            # AWS access key id
    r"AIza[0-9A-Za-z_\-]{20,}",                     # Google API key
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",          # PEM private key
]


def validate_files(files: dict[str, str], max_bytes: int, max_files: int = 500,
                   max_file_bytes: int | None = None) -> None:
    from .config import settings
    per_file = max_file_bytes if max_file_bytes is not None else settings.max_file_bytes
    if not files:
        raise BundleError("empty bundle")
    if len(files) > max_files:
        raise BundleError(f"too many files (>{max_files})")
    total = 0
    for path, content in files.items():
        if not isinstance(path, str) or not isinstance(content, str):
            raise BundleError("paths and contents must be strings")
        if path.startswith("/") or path.startswith("\\"):
            raise BundleError(f"absolute path not allowed: {path}")
        norm = normpath(path)
        if norm.startswith("..") or norm.startswith("/") or ".." in norm.split("/"):
            raise BundleError(f"path escapes bundle root: {path}")
        size = len(content.encode("utf-8"))
        if size > per_file:
            raise BundleError(f"file too large: {path} ({size} > {per_file} bytes)")
        total += size
    if total > max_bytes:
        raise BundleError(f"bundle too large ({total} > {max_bytes} bytes)")


def pack(files: dict[str, str]) -> bytes:
    # Deterministic: tar entries sorted with mtime=0, AND the gzip header mtime
    # pinned to 0 (the default embeds the current time, breaking reproducibility).
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(files):
                data = files[path].encode("utf-8")
                info = tarfile.TarInfo(name=path)
                info.size = len(data)
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def unpack(data: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        for info in tar.getmembers():
            if not info.isfile():
                continue
            out[info.name] = tar.extractfile(info).read().decode("utf-8")
    return out


def _walk_commands(node):
    """Collect every {'command': ...} string found anywhere in a hooks.json tree."""
    found = []
    if isinstance(node, dict):
        if isinstance(node.get("command"), str):
            found.append(node["command"])
        for v in node.values():
            found += _walk_commands(v)
    elif isinstance(node, list):
        for v in node:
            found += _walk_commands(v)
    return found


def effects_manifest(files: dict[str, str]) -> dict:
    hooks = []
    if "hooks/hooks.json" in files:
        try:
            tree = json.loads(files["hooks/hooks.json"]).get("hooks", {})
            for event, entries in tree.items():
                for cmd in _walk_commands(entries):
                    hooks.append({"event": event, "command": cmd})
        except (ValueError, AttributeError):
            pass

    mcp_servers = []
    if ".mcp.json" in files:
        try:
            servers = json.loads(files[".mcp.json"]).get("mcpServers", {})
            for name, cfg in servers.items():
                mcp_servers.append({
                    "name": name,
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                })
        except (ValueError, AttributeError):
            pass

    plugins = []
    if "plugins.json" in files:
        try:
            doc = json.loads(files["plugins.json"])
            markets = doc.get("marketplaces", {})
            for p in doc.get("plugins", []):
                if not p.get("enabled", True):
                    continue
                mk = markets.get(p.get("marketplace", ""), {})
                plugins.append({
                    "name": p.get("name", ""),
                    "marketplace": p.get("marketplace", ""),
                    "source": mk.get("repo", ""),
                })
        except (ValueError, AttributeError):
            pass

    counts = {
        "skills": sum(1 for p in files if p.startswith("skills/") and p.endswith("SKILL.md")),
        "commands": sum(1 for p in files if p.startswith("commands/")),
        "agents": sum(1 for p in files if p.startswith("agents/")),
        "rules": sum(1 for p in files if p == "CLAUDE.md" or p.startswith(".claude/rules/")),
        "plugins": len(plugins),
    }

    secret_flags = []
    for path, content in files.items():
        for pat in SECRET_PATTERNS:
            if re.search(pat, content):
                secret_flags.append(f"{path}: matched {pat}")
                break

    return {
        "hooks": hooks,
        "mcp_servers": mcp_servers,
        "plugins": plugins,
        "counts": counts,
        "runs_code": bool(hooks or mcp_servers or plugins),
        "secret_flags": secret_flags,
    }


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "setup"
