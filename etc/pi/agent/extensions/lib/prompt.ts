export const ADDITIONAL_USER_INSTRUCTIONS_TAG = "additional_user_instructions";
export const ADDITIONAL_USER_NOTES_TAG = "additional_user_notes";

function escapeClosingTag(content: string, tagName: string): string {
  return content.replaceAll(`</${tagName}>`, `<\\/${tagName}>`);
}

export function formatXmlLikeBlock(tagName: string, content: string): string {
  return `<${tagName}>\n${escapeClosingTag(content, tagName)}\n</${tagName}>`;
}

export function formatAdditionalUserInstructionsBlock(content: string): string {
  return formatXmlLikeBlock(ADDITIONAL_USER_INSTRUCTIONS_TAG, content);
}

export function formatAdditionalUserNotesBlock(content: string): string {
  return formatXmlLikeBlock(ADDITIONAL_USER_NOTES_TAG, content);
}
