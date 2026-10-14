import re

from django.test import Client, TestCase, override_settings
from django.urls import get_resolver
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import validate_spec

from news.api.openapi import build_spec
from news.api.services import MAX_PAGE_SIZE, STATUSES


def walk_routes(patterns, prefix=""):
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if hasattr(pattern, "url_patterns"):
            yield from walk_routes(pattern.url_patterns, route)
        else:
            yield route


def normalize(route):
    """Treat any URL converter/placeholder as an opaque segment."""
    return re.sub(r"(<[^>]+>|\{[^}]+\})", "{}", route).strip("/")


def iter_schemas(node, path=""):
    if isinstance(node, dict):
        if "$ref" in node:
            yield path, node["$ref"]
        for key, value in node.items():
            yield from iter_schemas(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_schemas(value, f"{path}/{index}")


def iter_operations(spec):
    for path, item in spec["paths"].items():
        for method, operation in item.items():
            yield path, method, operation


class OpenApiSpecTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_spec_is_served_raw_and_public(self):
        with override_settings(NEWS_API_KEY="secret-key"):
            response = self.client.get("/api/v1/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        self.assertNotIn("data", payload, "spec must not use the data envelope")
        self.assertEqual(payload["openapi"], "3.0.3")
        self.assertEqual(payload["info"]["title"], "AI News Scraper API")

        response = self.client.post("/api/v1/openapi.json")
        self.assertEqual(response.status_code, 405)

    def test_docs_page_serves_swagger_ui(self):
        with override_settings(NEWS_API_KEY="secret-key"):
            response = self.client.get("/api/v1/docs/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        content = response.content.decode()
        self.assertIn("swagger-ui-bundle.js", content)
        self.assertIn("swagger-ui.css", content)
        self.assertIn("/api/v1/openapi.json", content)
        self.assertIn('id="swagger-ui"', content)

        response = self.client.post("/api/v1/docs/")
        self.assertEqual(response.status_code, 405)

    def test_spec_is_structurally_valid(self):
        spec = build_spec()
        self.assertEqual(spec["security"], [{"apiKeyAuth": []}])
        self.assertIn("apiKeyAuth", spec["components"]["securitySchemes"])
        self.assertEqual(
            spec["components"]["securitySchemes"]["apiKeyAuth"]["name"],
            "X-API-Key",
        )

        tag_names = {tag["name"] for tag in spec["tags"]}
        operation_ids = []
        for path, method, operation in iter_operations(spec):
            with self.subTest(path=path, method=method):
                self.assertIn(operation.get("tags", [None])[0], tag_names)
                operation_ids.append(operation["operationId"])
                responses = operation["responses"]
                self.assertTrue(any(code.startswith("2") for code in responses))
                for code, response in responses.items():
                    self.assertTrue(response.get("description"), f"{code} lacks description")
                    self.assertIn("content", response)
                if path == "/api/v1/health/":
                    self.assertEqual(operation.get("security"), [], path)
                else:
                    self.assertNotIn("security", operation)
        self.assertEqual(len(operation_ids), len(set(operation_ids)), "operationId must be unique")

    def test_every_ref_resolves(self):
        spec = build_spec()
        for path, ref in iter_schemas(spec):
            with self.subTest(path=path, ref=ref):
                self.assertTrue(ref.startswith("#/"), ref)
                target = spec
                for part in ref.split("/")[1:]:
                    self.assertIn(part, target, f"unresolvable ref {ref}")
                    target = target[part]

    def test_spec_paths_match_urlconf(self):
        spec_paths = {normalize(path) for path in build_spec()["paths"]}
        routes = {
            normalize(route)
            for route in walk_routes(get_resolver().url_patterns)
            if route.startswith("api/v1/")
        }
        documented_routes = routes - {normalize("api/v1/docs/"), normalize("api/v1/openapi.json")}
        self.assertEqual(spec_paths, documented_routes)

    def test_path_template_parameters_are_declared(self):
        for path, _, operation in iter_operations(build_spec()):
            declared = set()
            for parameter in operation.get("parameters", []):
                target = _ref_target(parameter["$ref"]) if "$ref" in parameter else parameter
                if target.get("in") == "path":
                    declared.add(target.get("name"))
            placeholders = set(re.findall(r"\{([^}]+)\}", path))
            with self.subTest(path=path, operation=operation["operationId"]):
                self.assertEqual(placeholders, declared)

    def test_run_endpoint_documents_job_contract(self):
        spec = build_spec()
        post = spec["paths"]["/api/v1/pipeline/runs/"]["post"]
        body_schema = post["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        self.assertEqual(body_schema, "#/components/schemas/RunRequest")
        run_request = spec["components"]["schemas"]["RunRequest"]
        self.assertFalse(run_request["additionalProperties"])
        self.assertIn("limit", run_request["properties"])

        accepted = post["responses"]["202"]
        self.assertIn("Location", accepted["headers"])
        self.assertEqual(
            accepted["content"]["application/json"]["schema"]["properties"]["data"]["$ref"],
            "#/components/schemas/Run",
        )
        for status in ("400", "401", "409", "415", "500"):
            self.assertIn(status, post["responses"])

        run = spec["components"]["schemas"]["Run"]
        self.assertEqual(
            run["properties"]["status"]["enum"],
            ["queued", "running", "succeeded", "failed", "cancelled"],
        )

    def test_enums_match_server_validation(self):
        spec = build_spec()
        self.assertEqual(
            spec["components"]["parameters"]["StatusFilter"]["schema"]["enum"],
            sorted(STATUSES),
        )
        self.assertEqual(
            spec["components"]["schemas"]["ProcessedRow"]["properties"]["status"]["enum"],
            sorted(STATUSES),
        )
        self.assertEqual(
            spec["components"]["parameters"]["PageSize"]["schema"]["maximum"],
            MAX_PAGE_SIZE,
        )

    def test_document_passes_openapi_standard_validation(self):
        validate_spec(build_spec())

    def test_serialized_run_and_processed_results_match_documented_schemas(self):
        from news.api.jobs import PipelineJob
        from news.api.serializers import serialize_processed

        spec = build_spec()
        def validate(name, value):
            OAS30Validator({"$ref": f"#/components/schemas/{name}",
                            "components": spec["components"]}).validate(value)

        job = PipelineJob({"limit": None})
        validate("Run", job.to_dict())
        job.status = "failed"
        job.error = "Service unavailable"
        job.summary = {"processed": 1, "approved": 0, "rejected": 0, "failed": 1,
                       "by_status": {"FACT_EXTRACTION_FAILED": 1}}
        validate("Run", job.to_dict())
        for value in ("", "{}", "[]", '{"error": "Invalid response"}', "raw invalid output"):
            with self.subTest(value=value):
                row = serialize_processed({"status": "ARTICLE_REJECTED", "facts": value,
                                           "verification": value}, 0)
                validate("ProcessedRow", row)


def _ref_target(ref):
    target = build_spec()
    for part in ref.split("/")[1:]:
        target = target[part]
    return target
