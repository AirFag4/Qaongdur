const DEFAULT_LOCALE = "sv-SE";
const DATETIME_LOCAL_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

export const BANGKOK_TIME_ZONE = "Asia/Bangkok";
export const DEFAULT_OPERATOR_TIME_ZONE = BANGKOK_TIME_ZONE;
export const OPERATOR_TIME_ZONE_STORAGE_KEY = "qaongdur-operator-time-zone";
export const DEFAULT_OPERATOR_WINDOW_MINUTES = 10;

export type OperatorTimeZonePreference =
  | "browser-local"
  | "UTC"
  | "Asia/Bangkok"
  | "Asia/Tokyo"
  | "Europe/London"
  | "America/New_York";

const OPERATOR_TIME_ZONE_CHOICES: Array<{
  value: Exclude<OperatorTimeZonePreference, "browser-local">;
  label: string;
}> = [
  { value: "Asia/Bangkok", label: "Bangkok (UTC+7)" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Tokyo", label: "Tokyo" },
  { value: "Europe/London", label: "London" },
  { value: "America/New_York", label: "New York" },
];

const DATE_TIME_PARTS: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
};

const DATE_TIME_WITH_SECONDS_PARTS: Intl.DateTimeFormatOptions = {
  ...DATE_TIME_PARTS,
  second: "2-digit",
  timeZoneName: "short",
};

const TIME_WITH_SECONDS_PARTS: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZoneName: "short",
};

const dateTimePartFormatterCache = new Map<string, Intl.DateTimeFormat>();
const displayFormatterCache = new Map<string, Intl.DateTimeFormat>();

const isSupportedOperatorTimeZone = (
  value: string | null | undefined,
): value is OperatorTimeZonePreference =>
  value === "browser-local" ||
  OPERATOR_TIME_ZONE_CHOICES.some((choice) => choice.value === value);

export const getBrowserLocalTimeZone = () =>
  Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";

export const resolveOperatorTimeZone = (
  preference: OperatorTimeZonePreference,
) => (preference === "browser-local" ? getBrowserLocalTimeZone() : preference);

export const getOperatorTimeZonePreference = () => {
  if (typeof window === "undefined") {
    return DEFAULT_OPERATOR_TIME_ZONE;
  }
  const stored = window.localStorage.getItem(OPERATOR_TIME_ZONE_STORAGE_KEY);
  return isSupportedOperatorTimeZone(stored)
    ? stored
    : DEFAULT_OPERATOR_TIME_ZONE;
};

export const getOperatorTimeZoneOptions = (): Array<{
  value: OperatorTimeZonePreference;
  label: string;
}> => [
  {
    value: "browser-local",
    label: `Browser local (${getBrowserLocalTimeZone()})`,
  },
  ...OPERATOR_TIME_ZONE_CHOICES,
];

export const getOperatorTimeZoneLabel = (
  preference: OperatorTimeZonePreference,
) => {
  if (preference === "browser-local") {
    return `Browser local (${getBrowserLocalTimeZone()})`;
  }
  return (
    OPERATOR_TIME_ZONE_CHOICES.find((choice) => choice.value === preference)
      ?.label ?? preference
  );
};

const getPartsFormatter = (timeZone: string) => {
  const cacheKey = `${DEFAULT_LOCALE}:${timeZone}:parts`;
  const cached = dateTimePartFormatterCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const formatter = new Intl.DateTimeFormat(DEFAULT_LOCALE, {
    timeZone,
    ...DATE_TIME_WITH_SECONDS_PARTS,
  });
  dateTimePartFormatterCache.set(cacheKey, formatter);
  return formatter;
};

const getDisplayFormatter = (
  timeZone: string,
  options: Intl.DateTimeFormatOptions,
) => {
  const cacheKey = `${DEFAULT_LOCALE}:${timeZone}:${JSON.stringify(options)}`;
  const cached = displayFormatterCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const formatter = new Intl.DateTimeFormat(DEFAULT_LOCALE, {
    timeZone,
    ...options,
  });
  displayFormatterCache.set(cacheKey, formatter);
  return formatter;
};

const toValidDate = (value: Date | string | number) => {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const getTimeZoneParts = (date: Date, timeZone: string) => {
  const parts = getPartsFormatter(timeZone).formatToParts(date);
  const lookup = Object.fromEntries(
    parts
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );

  return {
    year: Number(lookup.year),
    month: Number(lookup.month),
    day: Number(lookup.day),
    hour: Number(lookup.hour),
    minute: Number(lookup.minute),
    second: Number(lookup.second),
  };
};

const getTimeZoneOffsetMs = (date: Date, timeZone: string) => {
  const parts = getTimeZoneParts(date, timeZone);
  const utcTimestamp = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour,
    parts.minute,
    parts.second,
  );
  return utcTimestamp - date.getTime();
};

export const formatDateTimeInputForTimeZone = (
  value: Date | string | number,
  preference: OperatorTimeZonePreference,
) => {
  const date = toValidDate(value);
  if (!date) {
    return "";
  }

  const timeZone = resolveOperatorTimeZone(preference);
  const parts = getTimeZoneParts(date, timeZone);
  return `${String(parts.year).padStart(4, "0")}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}T${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`;
};

export const parseDateTimeInputInTimeZone = (
  value: string,
  preference: OperatorTimeZonePreference,
) => {
  const match = DATETIME_LOCAL_PATTERN.exec(value.trim());
  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute] = match;
  const timeZone = resolveOperatorTimeZone(preference);
  const targetUtcMillis = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour),
    Number(minute),
    0,
  );

  let candidateMillis = targetUtcMillis;
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const offset = getTimeZoneOffsetMs(new Date(candidateMillis), timeZone);
    const nextCandidate = targetUtcMillis - offset;
    if (nextCandidate === candidateMillis) {
      break;
    }
    candidateMillis = nextCandidate;
  }

  const candidate = new Date(candidateMillis);
  return formatDateTimeInputForTimeZone(candidate, preference) === value.trim()
    ? candidate
    : null;
};

export const toIsoOrUndefinedInTimeZone = (
  value: string,
  preference: OperatorTimeZonePreference,
) => {
  const parsed = parseDateTimeInputInTimeZone(value, preference);
  return parsed ? parsed.toISOString() : undefined;
};

export const createRecentInputRangeInTimeZone = (
  preference: OperatorTimeZonePreference,
  minutes = DEFAULT_OPERATOR_WINDOW_MINUTES,
) => {
  const { from, to } = createRecentAbsoluteRange(minutes);
  return {
    from,
    to,
    fromInput: formatDateTimeInputForTimeZone(from, preference),
    toInput: formatDateTimeInputForTimeZone(to, preference),
  };
};

export const createRecentAbsoluteRange = (
  minutes = DEFAULT_OPERATOR_WINDOW_MINUTES,
) => {
  const to = new Date();
  const from = new Date(to.getTime() - minutes * 60 * 1000);
  return {
    from,
    to,
  };
};

export const formatDateTimeInTimeZone = (
  value: Date | string | number,
  preference: OperatorTimeZonePreference,
  options?: { includeSeconds?: boolean },
) => {
  const date = toValidDate(value);
  if (!date) {
    return "n/a";
  }
  const timeZone = resolveOperatorTimeZone(preference);
  return getDisplayFormatter(
    timeZone,
    options?.includeSeconds ? DATE_TIME_WITH_SECONDS_PARTS : DATE_TIME_PARTS,
  ).format(date);
};

export const formatTimeInTimeZone = (
  value: Date | string | number,
  preference: OperatorTimeZonePreference,
) => {
  const date = toValidDate(value);
  if (!date) {
    return "n/a";
  }
  const timeZone = resolveOperatorTimeZone(preference);
  return getDisplayFormatter(timeZone, TIME_WITH_SECONDS_PARTS).format(date);
};

export const createRecentBangkokInputRange = (
  minutes = DEFAULT_OPERATOR_WINDOW_MINUTES,
) => createRecentInputRangeInTimeZone(BANGKOK_TIME_ZONE, minutes);

export const formatBangkokDateTimeInput = (value: Date | string | number) =>
  formatDateTimeInputForTimeZone(value, BANGKOK_TIME_ZONE);

export const parseBangkokDateTimeInput = (value: string) =>
  parseDateTimeInputInTimeZone(value, BANGKOK_TIME_ZONE);

export const toBangkokIsoOrUndefined = (value: string) =>
  toIsoOrUndefinedInTimeZone(value, BANGKOK_TIME_ZONE);

export const formatBangkokDateTime = (
  value: Date | string | number,
  options?: { includeSeconds?: boolean },
) => formatDateTimeInTimeZone(value, BANGKOK_TIME_ZONE, options);

export const formatBangkokTime = (value: Date | string | number) =>
  formatTimeInTimeZone(value, BANGKOK_TIME_ZONE);
