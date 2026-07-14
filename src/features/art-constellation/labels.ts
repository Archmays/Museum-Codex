import type { Translation } from "../../i18n/translations";
import type { RelationshipRecord } from "./types";

export function relationshipTypeLabel(
  type: RelationshipRecord["type"],
  copy: Translation["constellation"],
) {
  return {
    shared_subject: copy.sharedSubject,
    shared_material: copy.sharedMaterial,
    shared_technique: copy.sharedTechnique,
  }[type];
}
