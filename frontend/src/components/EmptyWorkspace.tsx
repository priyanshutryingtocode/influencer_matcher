import { EmptyState } from "./EmptyState";
import { pipelineStages } from "./RunStatus";

export function EmptyWorkspace() {
  return (
    <EmptyState
      index="READY"
      title="Set a brief."
      body="Retrieval, semantic matching, and ranking stay visible here while the run moves through each stage."
      steps={pipelineStages.map((stage) => stage.label)}
    />
  );
}
