import { IsString, MinLength } from 'class-validator';

export class AdminChangePasswordDto {
  @IsString()
  @MinLength(8, { message: 'Пароль не менее 8 символов' })
  newPassword!: string;
}
