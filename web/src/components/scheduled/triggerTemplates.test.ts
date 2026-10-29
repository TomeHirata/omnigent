import { describe, expect, it } from "vitest";
import {
  renderTriggerPrompt,
  triggerFieldsComplete,
  type TriggerFields,
  type TriggerPromptContext,
} from "./triggerTemplates";

const CTX: TriggerPromptContext = {
  placement: "same_host",
  sessionLinkBase: "https://omni.example.com/c/",
};

function fields(overrides: Partial<TriggerFields> = {}): TriggerFields {
  return {
    watch: "project = ES AND labels = omnigent",
    filter: "",
    instructions: "Investigate the ticket.",
    linkBack: true,
    ...overrides,
  };
}

describe("triggerFieldsComplete", () => {
  it("needs a watch value and instructions, but not a filter", () => {
    expect(triggerFieldsComplete(fields())).toBe(true);
    expect(triggerFieldsComplete(fields({ watch: "  " }))).toBe(false);
    expect(triggerFieldsComplete(fields({ instructions: "" }))).toBe(false);
  });
});

describe("renderTriggerPrompt", () => {
  it("renders the Jira manager prompt with the JQL, placement, dedupe title and link", () => {
    const prompt = renderTriggerPrompt("jira", fields(), CTX);

    expect(prompt).toContain(
      "Watch: Jira tickets matching this JQL:\nproject = ES AND labels = omnigent",
    );
    expect(prompt).toContain(
      "search for (project = ES AND labels = omnigent) AND updated >= <that time>",
    );
    // The kept session dedupes against its own workers by title.
    expect(prompt).toContain("created_by_session_id is your session ID");
    expect(prompt).toContain('title "Jira <ticket key>"');
    expect(prompt).toContain('placement "same_host"');
    expect(prompt).toContain(
      'Comment "Omnigent session: https://omni.example.com/c/<conversation_id>" on each ticket',
    );
    expect(prompt).toContain('End with "Checked through: <time>"');
    expect(prompt.endsWith("Instructions for each session:\nInvestigate the ticket.")).toBe(true);
  });

  it("numbers the steps without a link-back step when it is off", () => {
    const prompt = renderTriggerPrompt("jira", fields({ linkBack: false }), CTX);

    expect(prompt).not.toContain("Omnigent session:");
    expect(prompt).toContain("\n5. Reply with the sessions you started.");
  });

  it("passes the task's model and effort to each worker", () => {
    const prompt = renderTriggerPrompt("jira", fields(), {
      ...CTX,
      placement: "managed",
      model: "claude-opus",
      effort: "high",
    });

    expect(prompt).toContain('placement "managed"');
    expect(prompt).toContain('model "claude-opus", reasoning_effort "high"');
  });

  it("renders the Slack filter, or counts every top-level message without one", () => {
    const filtered = renderTriggerPrompt(
      "slack",
      fields({ watch: "#eng-support", filter: "report a bug" }),
      CTX,
    );
    expect(filtered).toContain("Watch: Slack messages in #eng-support that report a bug");
    expect(filtered).toContain("Only messages that report a bug count.");
    expect(filtered).toContain('title "Slack <channel> <message ts>"');
    expect(filtered).toContain("in the thread of each message");

    const unfiltered = renderTriggerPrompt("slack", fields({ watch: "#eng-support" }), CTX);
    expect(unfiltered).toContain("Watch: Slack messages in #eng-support\n");
    expect(unfiltered).toContain("Every top-level message counts.");
  });

  it("builds the GitHub search from the repository and optional filter", () => {
    const prompt = renderTriggerPrompt(
      "github",
      fields({ watch: "acme/app", filter: "is:issue label:bug" }),
      CTX,
    );
    expect(prompt).toContain("search for: repo:acme/app is:issue label:bug updated:>=<that time>");
    expect(prompt).toContain('title "GitHub <owner/repo>#<number>"');

    const unfiltered = renderTriggerPrompt("github", fields({ watch: "acme/app" }), CTX);
    expect(unfiltered).toContain("search for: repo:acme/app updated:>=<that time>");
  });
});
