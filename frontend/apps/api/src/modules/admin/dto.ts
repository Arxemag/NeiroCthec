import { IsString, MinLength } from '../../lib/validators';

export class AdminChangePasswordDto {
  @IsString()
  @MinLength(8, { message: 'Пароль не менее 8 символов' })
  newPassword!: string;
}
