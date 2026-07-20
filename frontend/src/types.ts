export interface LinkOut {
  id: string;
  slug: string;
  marketplace: string;
  title: string;
  image_url: string;
  views: number;
  clicks: number;
  created_at: string;
  article_url: string;
  revoked?: boolean;
  tagged_url?: string;
}

export interface SeriesDay {
  date: string;
  views: number;
  clicks: number;
  links: number;
}

export interface Overview {
  totals: { views: number; clicks: number; links: number; orders: number; conversion: number };
  today: { views: number; clicks: number; links: number };
  week: { views: number; clicks: number };
  series: SeriesDay[];
  top: LinkOut[];
  recent: LinkOut[];
}

export interface Me {
  username: string;
  whatsapp_number: string;
  name: string;
  store_name: string;
  link_preference: "direct" | "hub";
  avatar: string;
  store_slug: string;
  store_enabled: boolean;
  bank: string;
  account_title: string;
  account_number: string;
}

export type CheckStatus = "unregistered" | "unclaimed" | "claimed";

export interface WaStatus {
  primary: string;
  linked: string[];
  max: number;
  bot_number: string;
}

export interface MyEarnings {
  earned: number;
  paid: number;
  balance: number;
  min_payout: number;
  referrals: { referred_name: string; amount: number; created_at: string }[];
  entries: { kind: string; amount: number; label: string; created_at: string }[];
  payouts: { amount: number; paid_at: string; note: string }[];
}

