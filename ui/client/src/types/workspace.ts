export interface ElementCategory {
  category: string;
  elements: ElementType[];
}

export interface ElementType {
  category: string;
  name: string;
  type: string;
  hints?: Array<{
    hint_type: string;
    reason?: string;
  }>;
}

export interface ElementInstance {
  rid: string;
  name?: string;
  config?: any;
  category?: string;
  type?: string;
  version?: number;
  created?: string;
  updated?: string;
  nested_refs?: string[];
}

export interface ElementSchema {
  category: string;
  name: string;
  type: string;
  description: string;
  tags: string[];
  config_schema: {
    type: string;
    properties: { [key: string]: any };
    required: string[];
    additionalProperties: boolean;
    $defs?: { [key: string]: any };
  };
}

export interface CatalogResponse {
  elements: {
    [category: string]: ElementType[];
  };
}

export interface RefField {
  $ref: string;
  category: string;
  description: string;
  examples: string[];
}