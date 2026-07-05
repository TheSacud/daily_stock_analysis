import camelcaseKeys from 'camelcase-keys';

/**
 * Converts snake_case object keys to camelCase
 * @param data API response data (snake_case)
 * @returns Converted camelCase object
 */
export function toCamelCase<T>(data: unknown): T {
    if (data === null || data === undefined) {
        return data as T;
    }
    return camelcaseKeys(data as Record<string, unknown>, { deep: true }) as T;
}
