import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "@/components/states";
import { postStatusLabel } from "@/lib/labels";

describe("labels", () => {
  it("names the approval state in Russian", () => {
    expect(postStatusLabel("PENDING_APPROVAL")).toBe("Ждёт одобрения");
    expect(postStatusLabel("UNKNOWN")).toBe("Нужна проверка");
  });
});

describe("empty state", () => {
  it("shows a title and explanation", () => {
    render(<EmptyState title="Очередь пуста" body="Новые посты появятся после генерации." />);
    expect(screen.getByRole("heading", { name: "Очередь пуста" })).toBeInTheDocument();
    expect(screen.getByText("Новые посты появятся после генерации.")).toBeInTheDocument();
  });
});
