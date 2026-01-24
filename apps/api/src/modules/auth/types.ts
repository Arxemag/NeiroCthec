import { UserRole, SubscriptionStatus } from '@prisma/client';

export type JwtAccessPayload = {
  sub: string;
  email: string;
  role: UserRole;
  subscriptionStatus: SubscriptionStatus;
};

export type JwtRefreshPayload = {
  sub: string;
  tokenId: string;
};

