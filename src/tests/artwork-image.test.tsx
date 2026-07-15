import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ArtworkImage } from "../features/art-constellation/ArtworkImage";
import type { MediaAsset } from "../features/art-constellation/types";

const baseAsset: MediaAsset = {
  id: "media:met-1-320w-jpeg",
  artworkId: "artwork:met-1",
  parentMediaId: "media:met-1-original",
  src: "http://localhost:3000/Museum-Codex/releases/art-constellation-1.0.0/assets/met-1/320w.jpg",
  publicPath: "assets/met-1/320w.jpg",
  format: "jpeg",
  mimeType: "image/jpeg",
  width: 320,
  height: 480,
  bytes: 1234,
  sha256: `sha256:${"a".repeat(64)}`,
  role: "thumbnail",
  attribution: "The Metropolitan Museum of Art, CC0",
  changesStatement: "Resized and compressed; artwork content unchanged.",
  licenseIdentifier: "CC0-1.0",
  licenseUrl: "https://creativecommons.org/publicdomain/zero/1.0/",
  sourceUrl: "https://www.metmuseum.org/art/collection/search/1",
  withdrawalStatus: "active",
  withdrawalNotice: "Remove this derivative from a future release if its status changes.",
};

const commonProps = {
  artworkId: "artwork:met-1",
  representativeMediaId: "media:met-1-640w-webp",
  alt: "Example work — Example artist",
  noImageText: "No approved image",
  lowBandwidthText: "No image request until selected",
  loadImageText: "Load image",
  imageLoadingText: "Loading image",
  imageLoadedText: "Image loaded",
  unavailableText: "Image unavailable",
  rightsLabel: "Rights:",
  withdrawalLabel: "Withdrawal:",
  officialSourceLabel: "Official source",
  officialSourceUrl: "https://www.metmuseum.org/art/collection/search/1",
};

describe("ArtworkImage", () => {
  it("creates no image request in low-bandwidth mode until explicit activation", async () => {
    const user = userEvent.setup();
    const media: MediaAsset[] = [
      baseAsset,
      { ...baseAsset, id: "media:met-1-640w-jpeg", src: baseAsset.src.replace("320w", "640w"), publicPath: "assets/met-1/640w.jpg", width: 640 },
      { ...baseAsset, id: "media:met-1-320w-webp", src: baseAsset.src.replace("320w.jpg", "320w.webp"), publicPath: "assets/met-1/320w.webp", format: "webp", mimeType: "image/webp" },
      { ...baseAsset, id: "media:met-1-640w-webp", src: baseAsset.src.replace("320w.jpg", "640w.webp"), publicPath: "assets/met-1/640w.webp", format: "webp", mimeType: "image/webp", width: 640 },
    ];
    const { container } = render(<ArtworkImage {...commonProps} media={media} lowBandwidth />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("source")).toBeNull();

    await user.click(screen.getByRole("button", { name: "Load image" }));
    const status = screen.getByRole("status");
    expect(status).toHaveFocus();
    expect(status).toHaveTextContent("Loading image");
    const image = screen.getByRole("img", { name: commonProps.alt });
    expect(image).toHaveAttribute("loading", "lazy");
    expect(image).toHaveAttribute("decoding", "async");
    expect(image).toHaveAttribute("srcset", expect.stringContaining("320w.jpg 320w"));
    expect(container.querySelector('source[type="image/webp"]')).toHaveAttribute(
      "srcset",
      expect.stringContaining("640w.webp 640w"),
    );
    expect(screen.getByText(/The Metropolitan Museum of Art/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "CC0-1.0" })).toHaveAttribute("href", baseAsset.licenseUrl);
    fireEvent.load(image);
    expect(status).toHaveTextContent("Image loaded");
  });

  it("rejects non-release and cross-origin image URLs", () => {
    const remote = { ...baseAsset, src: "https://images.example.org/320w.jpg" };
    const { container } = render(<ArtworkImage {...commonProps} media={[remote]} lowBandwidth={false} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("img", { name: "No approved image" })).toBeInTheDocument();
  });

  it("falls back to metadata when decoding fails", () => {
    const { container } = render(<ArtworkImage {...commonProps} media={[baseAsset]} lowBandwidth={false} />);
    const image = screen.getByRole("img", { name: commonProps.alt });
    fireEvent.error(image);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByRole("status")).toHaveTextContent("Image unavailable");
  });
});
