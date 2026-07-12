from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

from museum_pipeline import __version__
from museum_pipeline.config import USER_AGENT, source_configuration, source_license_rules
from museum_pipeline.errors import PipelineError


SENSITIVE_NAMES = {"api_key", "apikey", "key", "token", "access_token", "authorization", "cookie"}


@dataclass(frozen=True)
class RequestSpec:
    method: str
    url: str
    headers: dict[str, str]
    query_profile: str
    credential_alias: str | None = None


@dataclass(frozen=True)
class ResponseContract:
    status_code: int
    headers: dict[str, str]
    body: bytes
    final_url: str
    redirect_chain: tuple[str, ...] = ()
    retry_count: int = 0


class SourceAdapter(ABC):
    adapter_version = __version__
    contract_version = "1.0.0"
    credential_requirements = "none"
    supported_record_types: tuple[str, ...] = ()
    object_id_pattern = re.compile(r"^$")
    source_id = ""
    adapter_name = ""

    @property
    def configuration(self) -> dict[str, Any]:
        return source_configuration(self.source_id)

    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        return tuple(self.configuration["allowed_hosts"])

    def validate_object_id(self, object_id: str) -> str:
        if self.object_id_pattern.fullmatch(object_id) is None:
            raise PipelineError("object_id_invalid", f"Invalid object ID for {self.source_id}")
        return object_id

    def validate_request(self, request: RequestSpec) -> None:
        parsed = urlsplit(request.url)
        if request.method != "GET":
            raise PipelineError("method_not_allowed", "Adapters may issue GET requests only")
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts:
            raise PipelineError("endpoint_not_allowed", "Request endpoint is outside the adapter allowlist")
        if parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment:
            raise PipelineError("endpoint_not_allowed", "Request endpoint contains forbidden authority data")
        normalized_path = parsed.path
        for _ in range(4):
            decoded = unquote(normalized_path)
            if decoded == normalized_path:
                break
            normalized_path = decoded
        if re.fullmatch(str(self.configuration["allowed_path_pattern"]), normalized_path) is None:
            raise PipelineError("endpoint_path_not_allowed", "Request path is outside the adapter contract")
        query_names = {name.lower() for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        if query_names & SENSITIVE_NAMES:
            raise PipelineError("secret_in_url", "Credential values may not appear in request URLs")
        if query_names - set(self.configuration.get("allowed_query_names", [])):
            raise PipelineError("query_parameter_not_allowed", "Request includes an unapproved query parameter")
        if self.credential_requirements == "none" and any(name.lower() in SENSITIVE_NAMES for name in request.headers):
            raise PipelineError("credential_header_forbidden", "This source adapter does not accept credential headers")

    @abstractmethod
    def build_request(self, object_id: str, *, query_profile: str = "default") -> RequestSpec:
        raise NotImplementedError

    def redact_request(self, request: RequestSpec) -> dict[str, Any]:
        self.validate_request(request)
        parsed = urlsplit(request.url)
        safe_query = [
            (name, "[REDACTED]" if name.lower() in SENSITIVE_NAMES else value)
            for name, value in parse_qsl(parsed.query, keep_blank_values=True)
        ]
        safe_url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query), ""))
        headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in SENSITIVE_NAMES
        }
        return {
            "method": request.method,
            "canonical_endpoint": safe_url,
            "headers": dict(sorted(headers.items())),
            "query_profile": request.query_profile,
            "credential_alias": request.credential_alias,
        }

    def decode_json(self, response: ResponseContract) -> Any:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in {"application/json", "application/ld+json", "application/vnd.api+json"}:
            raise PipelineError("content_type_invalid", f"Unexpected response content type: {content_type or 'missing'}")
        try:
            return json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PipelineError("response_json_invalid", "Response body is not valid UTF-8 JSON") from error

    @abstractmethod
    def validate_response_contract(self, response: ResponseContract) -> Any:
        raise NotImplementedError

    @abstractmethod
    def extract_source_object_ids(self, document: Any) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, document: Any, *, snapshot_id: str, observed_at: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def map_license_rules(self, fields: list[str]) -> dict[str, str]:
        raise NotImplementedError

    @abstractmethod
    def extract_media_candidates(self, document: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def detect_contract_drift(self, document: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def rule(self, content_class: str, *, field: str | None = None) -> dict[str, Any]:
        rules = [rule for rule in source_license_rules(self.source_id) if rule["content_class"] == content_class]
        if field == "description":
            rules = [
                rule for rule in rules
                if rule.get("scope_match", {}).get("field_policy") == "include"
                and "description" in rule.get("scope_match", {}).get("fields", [])
            ]
        elif self.source_id == "aic_api" and content_class in {"metadata", "data"}:
            rules = [rule for rule in rules if rule.get("scope_match", {}).get("field_policy") == "exclude"]
        if len(rules) != 1:
            raise PipelineError("license_rule_ambiguous", f"Cannot select one canonical {content_class} rule")
        return rules[0]

    def default_headers(self) -> dict[str, str]:
        return {"Accept": "application/json", "User-Agent": USER_AGENT}

    def contract_record(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "id": f"adapter:{self.source_id}",
            "entity_type": "adapter_contract",
            "source_id": self.source_id,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "contract_version": self.contract_version,
            "allowed_hosts": list(self.allowed_hosts),
            "supported_record_types": list(self.supported_record_types),
            "credential_requirements": {"mode": self.credential_requirements, "aliases": []},
            "network_default_enabled": False,
            "methods": [
                "build_request", "redact_request", "validate_response_contract",
                "extract_source_object_ids", "normalize", "map_license_rules",
                "extract_media_candidates", "detect_contract_drift",
            ],
        }
