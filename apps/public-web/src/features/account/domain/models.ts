export interface AccountUser {
  id: string;
  name: string;
  email: string;
}

export interface NewsAccess {
  plan: string | null;
  status: string;
  accessAllowed: boolean;
  cancelAtPeriodEnd: boolean;
  accessEndsAt: string | null;
}

export interface AccountSession {
  user: AccountUser;
  news: NewsAccess;
}

export interface LoginInput {
  email: string;
  password: string;
}

export interface RegisterInput extends LoginInput {
  name: string;
  passwordConfirmation: string;
}

export interface AccountUserDto {
  id: string | number;
  name: string;
  email: string;
}

export interface NewsAccessDto {
  plan: string | null;
  status: string;
  access_allowed: boolean;
  cancel_at_period_end: boolean;
  access_ends_at: string | null;
}

export function mapAccountSession(dto: { user: AccountUserDto; news: NewsAccessDto }): AccountSession {
  return {
    user: {
      id: String(dto.user.id),
      name: dto.user.name,
      email: dto.user.email
    },
    news: {
      plan: dto.news.plan,
      status: dto.news.status,
      accessAllowed: dto.news.access_allowed,
      cancelAtPeriodEnd: dto.news.cancel_at_period_end,
      accessEndsAt: dto.news.access_ends_at
    }
  };
}
