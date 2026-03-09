/**
 * Declarations for class-validator so TypeScript resolves decorators
 * even when the package's own types are not available (e.g. in Docker).
 */
declare module 'class-validator' {
  export function IsString(validationOptions?: object): PropertyDecorator;
  export function IsNumber(validationOptions?: object): PropertyDecorator;
  export function IsOptional(validationOptions?: object): PropertyDecorator;
  export function IsEmail(validationOptions?: object): PropertyDecorator;
  export function IsArray(validationOptions?: object): PropertyDecorator;
  export function IsObject(validationOptions?: object): PropertyDecorator;
  export function MinLength(min: number, validationOptions?: object): PropertyDecorator;
  export function MaxLength(max: number, validationOptions?: object): PropertyDecorator;
  export function Min(minValue: number, validationOptions?: object): PropertyDecorator;
  export function Max(maxValue: number, validationOptions?: object): PropertyDecorator;
  export function ArrayNotEmpty(validationOptions?: object): PropertyDecorator;
  export function ValidateNested(validationOptions?: object): PropertyDecorator;
}
