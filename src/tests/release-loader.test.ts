import physicalManifest from "../../fixtures/release-bundles/valid/minimal/manifest.json";
import { loadStaticRelease, releaseMessage } from "../data/release-loader";

function response(body: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("static release loader", () => {
  it("returns a natural missing state for an absent manifest", async () => {
    const logger = vi.fn();
    const result = await loadStaticRelease("/missing.json", vi.fn().mockResolvedValue(response({}, 404)), logger);
    expect(result).toEqual({ status: "missing" });
    expect(logger).toHaveBeenCalledWith("missing");
    expect(releaseMessage(result.status, "zh-CN")).toContain("正式馆藏正在整理");
  });

  it("loads the canonical manifest from the Python-validated physical release fixture", async () => {
    const result = await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response(physicalManifest)));
    expect(result.status).toBe("loaded");
  });

  it("rejects reviewed candidates and every other non-public lifecycle", async () => {
    const candidate = { ...physicalManifest, status: "reviewed", public_release: false };
    const defaultResult = await loadStaticRelease(
      "/manifest.json",
      vi.fn().mockResolvedValue(response(candidate)),
    );
    expect(defaultResult.status).toBe("failed");

    const draftResult = await loadStaticRelease(
      "/manifest.json",
      vi.fn().mockResolvedValue(response({ ...candidate, status: "draft" })),
    );
    expect(draftResult.status).toBe("failed");
  });

  it("reports a canonical release with no display records as an empty museum", async () => {
    const emptyHash = "0".repeat(64);
    const artifact = (path: string, recordType: string, recordIds: string[]) => ({
      path,
      sha256: emptyHash,
      bytes: 2,
      record_type: recordType,
      schema_path: null,
      record_ids: recordIds,
    });
    const emptyRelease = {
      schema_version: "1.0.0",
      id: "release:empty-museum-1.0.0",
      entity_type: "dataset_release",
      version: "1.0.0",
      schema_versions: { "common/dataset-release": "1.0.0" },
      build_version: "empty-museum-build-1",
      created_at: "2026-07-11T00:00:00Z",
      source_snapshot_at: "2026-07-11T00:00:00Z",
      content_hash: `sha256:${emptyHash}`,
      status: "publishable",
      predecessor: null,
      public_release: true,
      public_until: null,
      included_entity_ids: [],
      included_relationship_ids: [],
      included_claim_ids: [],
      included_evidence_ids: [],
      included_source_ids: [],
      included_media_asset_ids: [],
      withdrawals: [],
      deprecations: [],
      manifest_files: [
        artifact("records.json", "data", []),
        artifact("source-rules-snapshot.json", "source_registry", []),
        artifact("license-decisions.json", "license_decisions", ["license-decision:code", "license-decision:content"]),
        artifact("third-party-notices.json", "third_party_notices", []),
        artifact("attributions.json", "attributions", []),
      ],
      license_decisions: {
        code_license_decision_id: "license-decision:code",
        code_license_status: "not_applicable",
        original_content_license_decision_id: "license-decision:content",
        original_content_license_status: "not_applicable",
        third_party_scope_statement: "No third-party collection content is included.",
        registry_path: "license-decisions.json",
        registry_sha256: emptyHash,
      },
      source_registry_manifest: { path: "source-rules-snapshot.json", sha256: emptyHash },
      third_party_notices_manifest: { path: "third-party-notices.json", sha256: emptyHash },
      attribution_manifest: { path: "attributions.json", sha256: emptyHash, asset_ids: [] },
      release_notes: "Canonical empty museum release.",
    };
    const result = await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response(emptyRelease)));
    expect(result.status).toBe("empty");
  });

  it("rejects an incompatible schema major without exposing internals", async () => {
    const logger = vi.fn();
    const result = await loadStaticRelease(
      "/manifest.json",
      vi.fn().mockResolvedValue(response({ ...physicalManifest, schema_version: "2.0.0" })),
      logger,
    );
    expect(result).toEqual({ status: "incompatible", foundVersion: "2.0.0" });
    expect(logger).toHaveBeenCalledWith("incompatible", "2.0.0");
    expect(releaseMessage(result.status, "en")).not.toMatch(/[A-Z]:\\|stack|exception/i);
  });

  it("rejects a minimal fake manifest", async () => {
    const fake = {
      schema_version: "1.0.0",
      version: "1.0.0",
      included_entity_ids: ["artist:example"],
      included_relationship_ids: [],
      included_claim_ids: [],
      included_media_asset_ids: [],
    };
    expect((await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response(fake)))).status).toBe("failed");
  });

  it.each([
    ["non-public lifecycle", { ...physicalManifest, status: "draft", public_release: false }],
    ["missing rights closure", { ...physicalManifest, third_party_notices_manifest: undefined }],
    ["missing file closure", { ...physicalManifest, manifest_files: [] }],
    ["invalid content hash", { ...physicalManifest, content_hash: "sha256:not-a-real-hash" }],
  ])("rejects %s", async (_label, manifest) => {
    const result = await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response(manifest)));
    expect(result.status).toBe("failed");
  });

  it.each([
    ["forged included ID", { ...physicalManifest, included_entity_ids: ["artist:fake"] }],
    [
      "missing license decision record",
      {
        ...physicalManifest,
        manifest_files: physicalManifest.manifest_files.map((file) =>
          file.record_type === "license_decisions" ? { ...file, record_ids: file.record_ids.slice(0, 1) } : file,
        ),
      },
    ],
    [
      "missing source registry record",
      {
        ...physicalManifest,
        manifest_files: physicalManifest.manifest_files.map((file) =>
          file.record_type === "source_registry" ? { ...file, record_ids: [] } : file,
        ),
      },
    ],
    [
      "missing media byte record",
      {
        ...physicalManifest,
        manifest_files: physicalManifest.manifest_files.map((file) =>
          file.record_type === "media" ? { ...file, record_ids: [] } : file,
        ),
      },
    ],
  ])("rejects %s closure", async (_label, manifest) => {
    const result = await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response(manifest)));
    expect(result.status).toBe("failed");
  });

  it("returns a controlled failure for network and malformed data", async () => {
    const networkFailure = await loadStaticRelease("/manifest.json", vi.fn().mockRejectedValue(new Error("private path")));
    const invalidData = await loadStaticRelease("/manifest.json", vi.fn().mockResolvedValue(response({ hello: "world" })));
    expect(networkFailure.status).toBe("failed");
    expect(invalidData.status).toBe("failed");
  });
});
