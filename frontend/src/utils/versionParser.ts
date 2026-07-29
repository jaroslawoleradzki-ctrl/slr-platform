const SEMVER_REGEX = /^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?$/;

export function parseAppVersion(rawContent: string | null | undefined): string {
  if (!rawContent) return 'development';
  const trimmed = rawContent.trim();
  if (!trimmed || !SEMVER_REGEX.test(trimmed)) {
    return 'development';
  }
  return trimmed;
}
