// Trigger section of the automation dialog, shown in place of the Prompt field
// while a Jira/Slack/GitHub template is active. See `triggerTemplates.ts`.

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/scheduled/Label";
import {
  MAX_INSTRUCTIONS_CHARS,
  MAX_SESSIONS_PER_RUN,
  TRIGGER_TEMPLATES,
  triggerServiceName,
  type TriggerFields,
  type TriggerSource,
} from "@/components/scheduled/triggerTemplates";

export function TriggerTemplateFields({
  source,
  fields,
  onChange,
  renderedPrompt,
  onEditAsPrompt,
}: {
  source: TriggerSource;
  fields: TriggerFields;
  onChange: (next: TriggerFields) => void;
  /** The prompt the task will save; "" until the required fields are filled. */
  renderedPrompt: string;
  /** Leave the template and edit the rendered prompt as a plain prompt. */
  onEditAsPrompt: () => void;
}) {
  const template = TRIGGER_TEMPLATES[source];
  const instructionsTooLong = fields.instructions.trim().length > MAX_INSTRUCTIONS_CHARS;
  return (
    <div className="flex flex-col gap-4" data-testid="task-trigger-fields">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="task-trigger-watch">{template.watchLabel}</Label>
        <Input
          id="task-trigger-watch"
          value={fields.watch}
          placeholder={template.watchPlaceholder}
          data-testid="task-trigger-watch"
          className="text-ui"
          onChange={(e) => onChange({ ...fields, watch: e.target.value })}
        />
      </div>

      {template.filterLabel !== null && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="task-trigger-filter">{template.filterLabel}</Label>
          <Input
            id="task-trigger-filter"
            value={fields.filter}
            placeholder={template.filterPlaceholder}
            data-testid="task-trigger-filter"
            className="text-ui"
            onChange={(e) => onChange({ ...fields, filter: e.target.value })}
          />
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="task-trigger-instructions">Instructions for each session</Label>
        <Textarea
          id="task-trigger-instructions"
          value={fields.instructions}
          rows={3}
          placeholder={template.instructionsPlaceholder}
          data-testid="task-trigger-instructions"
          componentId="tasks.scheduled.trigger_instructions"
          className="resize-none text-ui"
          onChange={(e) => onChange({ ...fields, instructions: e.target.value })}
        />
        {instructionsTooLong ? (
          <p className="text-sm text-destructive" role="alert" data-testid="task-trigger-too-long">
            Keep instructions to {MAX_INSTRUCTIONS_CHARS.toLocaleString("en-US")} characters or
            fewer so each session&apos;s first message has room for the item.
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">
            Each run looks for newly created {template.itemPlural} that match and starts one session
            for each, up to {MAX_SESSIONS_PER_RUN} per run. Older ones that change or start matching
            later don&apos;t.
          </p>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Checkbox
          id="task-trigger-link-back"
          checked={fields.linkBack}
          onCheckedChange={(checked) => onChange({ ...fields, linkBack: checked === true })}
          data-testid="task-trigger-link-back"
          componentId="tasks.scheduled.trigger_link_back"
        />
        <label htmlFor="task-trigger-link-back" className="cursor-pointer text-sm">
          {template.linkBackLabel}
        </label>
      </div>
      <p className="text-sm text-muted-foreground" data-testid="task-trigger-untrusted-note">
        Anyone who can write in what you watch can try to steer these sessions, which run with your
        tools.
        {fields.linkBack && ` Link-back posts to ${triggerServiceName(source)} with your account.`}
      </p>

      {renderedPrompt !== "" && (
        <details className="group" data-testid="task-trigger-preview">
          <summary className="cursor-pointer text-sm text-muted-foreground">Preview prompt</summary>
          <pre className="mt-2 max-h-56 overflow-y-auto rounded-md border border-border bg-muted/40 p-2 font-sans text-sm whitespace-pre-wrap">
            {renderedPrompt}
          </pre>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={onEditAsPrompt}
            data-testid="task-trigger-edit-as-prompt"
            componentId="tasks.scheduled.trigger_edit_as_prompt"
          >
            Edit as prompt
          </Button>
        </details>
      )}
    </div>
  );
}
