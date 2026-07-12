import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";

const forbiddenPublicTerms = ["Ready", "Not Ready", "Phase", "MVP", "Schema", "Fixture", "Release Gate", "Batch", "Development Only", "Placeholder", "TODO"];

describe("museum portal", () => {
  it("renders the home page with all seven museums and no internal status language", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "让知识的连接，成为参观的入口" })).toBeInTheDocument();
    for (const hall of ["美术馆", "生物馆", "音乐馆", "游戏馆", "文明馆", "武器博物馆", "科学馆"]) {
      expect(screen.getByRole("heading", { level: 3, name: hall })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(7);
    expect(screen.getByText("七个分馆")).toBeInTheDocument();
    const pageText = document.body.textContent ?? "";
    for (const term of forbiddenPublicTerms) expect(pageText).not.toContain(term);
  });

  it("only makes the Art Museum an available museum route", () => {
    render(<App />);
    expect(screen.getByRole("link", { name: /进入序厅/ })).toHaveAttribute("href", "#/art");
    for (const hall of ["生物馆", "音乐馆", "游戏馆", "文明馆", "武器博物馆", "科学馆"]) {
      expect(screen.queryByRole("link", { name: new RegExp(hall) })).not.toBeInTheDocument();
    }
  });

  it("keeps the Arms and Armor museum visible, explicitly preparing, and non-interactive", () => {
    render(<App />);
    const arms = screen.getByRole("article", { name: "武器博物馆，正在整理器物与历史线索" });
    expect(within(arms).getByRole("heading", { level: 3, name: "武器博物馆" })).toBeInTheDocument();
    expect(within(arms).getByText("Museum of Arms & Armor")).toBeInTheDocument();
    expect(within(arms).getByText("正在整理器物与历史线索")).toBeInTheDocument();
    expect(within(arms).queryByRole("link")).not.toBeInTheDocument();
    expect(arms.querySelector(".hall-motif-arms")).toHaveAttribute("aria-hidden", "true");
  });

  it("switches all core copy to reviewed English and persists the choice", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByRole("heading", { level: 1, name: "Let connections become the way in" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Art Museum/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Museum of Arms & Armor" })).toBeInTheDocument();
    expect(screen.getByText("Objects and historical threads in preparation")).toBeInTheDocument();
    expect(screen.getByText("Seven museums")).toBeInTheDocument();
    expect(localStorage.getItem("museum-locale")).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("does not create an Arms and Armor museum route", () => {
    window.location.hash = "#/arms";
    render(<App />);
    expect(screen.getByRole("heading", { level: 1, name: "这里还没有展厅" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "武器博物馆" })).not.toBeInTheDocument();
  });

  it("navigates to the Art Museum foyer with hash routing", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("link", { name: /进入序厅/ }));
    await waitFor(() => expect(window.location.hash).toBe("#/art"));
    expect(screen.getByRole("heading", { level: 1, name: "在一件作品前，打开许多条路" })).toBeInTheDocument();
    expect(screen.getByText("当前序厅介绍美术馆未来的探索方式，正式馆藏正在整理。")).toBeInTheDocument();
  });

  it("shows the current rights statement on the about route", () => {
    window.location.hash = "#/about";
    render(<App />);
    expect(screen.getByText(/除另有明确说明外，本项目内容未授予再利用许可/)).toBeInTheDocument();
    expect(screen.getByText(/第三方馆藏内容尚未上线/)).toBeInTheDocument();
  });

  it("provides a persistent low-bandwidth mode and reduced-motion hook", async () => {
    const user = userEvent.setup();
    window.location.hash = "#/accessibility";
    render(<App />);
    const control = screen.getByRole("button", { name: "开启低带宽模式" });
    await user.click(control);
    expect(document.documentElement).toHaveAttribute("data-bandwidth", "low");
    expect(localStorage.getItem("museum-low-bandwidth")).toBe("true");
    expect(document.documentElement).toHaveAttribute("data-motion", "full");
  });
});
