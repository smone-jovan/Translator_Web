export interface Chapter {
  id: number;
  order: number;
  title_original: string | null;
  title_translated: string | null;
  word_count: number;
  has_translation: boolean;
  translation_status?: string;
  is_bookmarked?: boolean;
}

export interface ThreadDetail {
  id: number;
  title: string;
  source_type: string;
  chapter_count: number;
  chapters: Chapter[];
  last_read_id?: number | null;
  cover_image?: string | null;
  original_title?: string | null;
  genres?: string | null;
  status?: string | null;
  status_coo?: string | null;
  synopsis?: string | null;
  author?: string | null;
}

export interface ChapterContent {
  id: number;
  order: number;
  title_original: string | null;
  title_translated: string | null;
  content_original: string | null;
  content_translated: string | null;
  translation_status: string | null;
  scroll_progress?: number;
  is_bookmarked?: boolean;
}
