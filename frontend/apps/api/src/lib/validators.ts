/**
 * Re-export class-validator via require() to avoid type resolution issues in Docker/workspace.
 */
// eslint-disable-next-line @typescript-eslint/no-require-imports
const cv = require('class-validator');

export const IsString = cv.IsString;
export const IsNumber = cv.IsNumber;
export const IsOptional = cv.IsOptional;
export const IsEmail = cv.IsEmail;
export const IsArray = cv.IsArray;
export const IsObject = cv.IsObject;
export const MinLength = cv.MinLength;
export const MaxLength = cv.MaxLength;
export const Min = cv.Min;
export const Max = cv.Max;
export const ArrayNotEmpty = cv.ArrayNotEmpty;
export const ValidateNested = cv.ValidateNested;
