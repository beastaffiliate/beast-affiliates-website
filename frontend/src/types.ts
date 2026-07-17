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
  totals: { views: number; clicks: number; links: number; conversion: number };
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
}

export type CheckStatus = "unregistered" | "unclaimed" | "claimed";
