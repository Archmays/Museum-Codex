import { createHash } from "node:crypto";

import {
  loadAssetResolutionManifest,
  type ReleaseManifest,
  type RuntimeAssetFile,
} from "../data/release-loader";

const hash = (value: string) => createHash("sha256").update(value).digest("hex");

function fixture(includedMediaIds = ["media:test-320w-jpeg"]) {
  const file: RuntimeAssetFile = {
    path: "releases/art-expansion-batch-01-1.5.0/assets/sha256/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.jpg",
    sha256: `sha256:${"a".repeat(64)}`,
    bytes: 123,
    record_type: "media",
    record_ids: ["media:test-320w-jpeg"],
    source_path: "data/reviewed/media/test.jpg",
    delivery_mode: "build_materialized",
  };
  const contentHash = `sha256:${hash(`${file.path}\0${file.sha256}\0${file.bytes}\n`)}`;
  const resolution = {
    id: "asset-resolution:art-expansion-1.5.0",
    schema_version: "1.0.0",
    release_id: "release:art-expansion-batch-01-1.5.0",
    content_hash: contentHash,
    referenced_files: [],
    materialized_asset_files: [file],
    referenced_file_count: 0,
    materialized_asset_count: 1,
    new_public_original_count: 0,
    runtime_external_image_request_count: 0,
  };
  const body = JSON.stringify(resolution);
  const manifest = {
    id: resolution.release_id,
    version: "1.5.0",
    included_media_asset_ids: includedMediaIds,
    manifest_files: [{
      path: "asset-resolution-manifest.json",
      sha256: `sha256:${hash(body)}`,
      bytes: body.length,
      record_type: "other",
      schema_path: null,
      record_ids: [resolution.id],
    }],
  } as unknown as ReleaseManifest;
  return { body, manifest };
}

describe("asset resolution loader", () => {
  it("verifies the declared file and the resolved media closure", async () => {
    const { body, manifest } = fixture();
    const result = await loadAssetResolutionManifest(
      new URL("https://museum.example/releases/art-expansion-batch-01-1.5.0/"),
      manifest,
      vi.fn().mockResolvedValue(new Response(body, { status: 200 })),
    );
    expect(result.materialized_asset_count).toBe(1);
    expect(result.materialized_asset_files[0]?.record_ids).toEqual(["media:test-320w-jpeg"]);
  });

  it("fails closed when the resolved media IDs do not match the release manifest", async () => {
    const { body, manifest } = fixture(["media:forged"]);
    await expect(loadAssetResolutionManifest(
      new URL("https://museum.example/releases/art-expansion-batch-01-1.5.0/"),
      manifest,
      vi.fn().mockResolvedValue(new Response(body, { status: 200 })),
    )).rejects.toThrow("asset_resolution_media_closure_invalid");
  });
});
