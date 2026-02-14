-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
/*
CREATE TABLE "alembic_version" (
	"version_num" varchar(32) PRIMARY KEY NOT NULL
);
--> statement-breakpoint
CREATE TABLE "parties" (
	"id" uuid PRIMARY KEY NOT NULL,
	"name" varchar NOT NULL,
	"owner_id" uuid NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "saved_rulings" (
	"id" uuid PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"query" text NOT NULL,
	"verdict_json" json NOT NULL,
	"privacy_level" varchar NOT NULL,
	"tags" json,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "subscriptions" (
	"id" uuid PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"stripe_customer_id" varchar NOT NULL,
	"stripe_subscription_id" varchar,
	"plan_tier" varchar NOT NULL,
	"status" varchar NOT NULL,
	"current_period_end" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "subscriptions_user_id_key" UNIQUE("user_id"),
	CONSTRAINT "subscriptions_stripe_customer_id_key" UNIQUE("stripe_customer_id"),
	CONSTRAINT "subscriptions_stripe_subscription_id_key" UNIQUE("stripe_subscription_id")
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" uuid PRIMARY KEY NOT NULL,
	"email" varchar NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"name" varchar,
	"email_verified" timestamp with time zone,
	"image" varchar,
	CONSTRAINT "users_email_key" UNIQUE("email")
);
--> statement-breakpoint
CREATE TABLE "file_blocklist" (
	"hash" varchar PRIMARY KEY NOT NULL,
	"reason" varchar NOT NULL,
	"reported_by" uuid,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "publishers" (
	"id" uuid PRIMARY KEY NOT NULL,
	"name" varchar NOT NULL,
	"slug" varchar NOT NULL,
	"api_key_hash" varchar NOT NULL,
	"contact_email" varchar NOT NULL,
	"verified" boolean NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "publishers_slug_key" UNIQUE("slug")
);
--> statement-breakpoint
CREATE TABLE "official_rulesets" (
	"id" uuid PRIMARY KEY NOT NULL,
	"publisher_id" uuid NOT NULL,
	"game_name" varchar NOT NULL,
	"game_slug" varchar NOT NULL,
	"source_type" varchar NOT NULL,
	"source_priority" integer NOT NULL,
	"version" varchar NOT NULL,
	"chunk_count" integer NOT NULL,
	"status" varchar NOT NULL,
	"pinecone_namespace" varchar NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "sessions" (
	"id" uuid PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"game_name" varchar NOT NULL,
	"active_ruleset_ids" uuid[],
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"expires_at" timestamp with time zone NOT NULL
);
--> statement-breakpoint
CREATE TABLE "user_game_library" (
	"id" uuid PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"game_name" varchar NOT NULL,
	"official_ruleset_ids" uuid[],
	"personal_ruleset_ids" uuid[],
	"is_favorite" boolean NOT NULL,
	"last_queried" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "query_audit_log" (
	"id" uuid PRIMARY KEY NOT NULL,
	"session_id" uuid,
	"user_id" uuid,
	"query_text" text NOT NULL,
	"expanded_query" text,
	"verdict_summary" text,
	"reasoning_chain" text,
	"confidence" double precision,
	"confidence_reason" text,
	"citation_ids" varchar[],
	"latency_ms" integer,
	"feedback" varchar,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "ruleset_metadata" (
	"id" uuid PRIMARY KEY NOT NULL,
	"session_id" uuid NOT NULL,
	"user_id" uuid NOT NULL,
	"filename" varchar NOT NULL,
	"game_name" varchar NOT NULL,
	"file_hash" varchar NOT NULL,
	"source_type" varchar NOT NULL,
	"source_priority" integer NOT NULL,
	"chunk_count" integer NOT NULL,
	"status" varchar NOT NULL,
	"error_message" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "accounts" (
	"id" uuid PRIMARY KEY NOT NULL,
	"user_id" uuid NOT NULL,
	"type" varchar NOT NULL,
	"provider" varchar NOT NULL,
	"provider_account_id" varchar NOT NULL,
	"refresh_token" text,
	"access_token" text,
	"expires_at" integer,
	"token_type" varchar,
	"scope" varchar,
	"id_token" text,
	"session_state" varchar,
	CONSTRAINT "uq_account_provider" UNIQUE("provider","provider_account_id")
);
--> statement-breakpoint
CREATE TABLE "auth_sessions" (
	"id" uuid PRIMARY KEY NOT NULL,
	"session_token" varchar NOT NULL,
	"user_id" uuid NOT NULL,
	"expires" timestamp with time zone NOT NULL,
	CONSTRAINT "auth_sessions_session_token_key" UNIQUE("session_token")
);
--> statement-breakpoint
CREATE TABLE "verification_tokens" (
	"identifier" varchar NOT NULL,
	"token" varchar NOT NULL,
	"expires" timestamp with time zone NOT NULL,
	CONSTRAINT "verification_tokens_pkey" PRIMARY KEY("identifier","token"),
	CONSTRAINT "verification_tokens_token_key" UNIQUE("token")
);
--> statement-breakpoint
CREATE TABLE "party_members" (
	"party_id" uuid NOT NULL,
	"user_id" uuid NOT NULL,
	"role" varchar NOT NULL,
	"joined_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "party_members_pkey" PRIMARY KEY("party_id","user_id")
);
--> statement-breakpoint
ALTER TABLE "parties" ADD CONSTRAINT "parties_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "saved_rulings" ADD CONSTRAINT "saved_rulings_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "subscriptions" ADD CONSTRAINT "subscriptions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "file_blocklist" ADD CONSTRAINT "file_blocklist_reported_by_fkey" FOREIGN KEY ("reported_by") REFERENCES "public"."users"("id") ON DELETE no action ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "official_rulesets" ADD CONSTRAINT "official_rulesets_publisher_id_fkey" FOREIGN KEY ("publisher_id") REFERENCES "public"."publishers"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "sessions" ADD CONSTRAINT "sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "user_game_library" ADD CONSTRAINT "user_game_library_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "query_audit_log" ADD CONSTRAINT "query_audit_log_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "query_audit_log" ADD CONSTRAINT "query_audit_log_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE set null ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ruleset_metadata" ADD CONSTRAINT "ruleset_metadata_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ruleset_metadata" ADD CONSTRAINT "ruleset_metadata_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "accounts" ADD CONSTRAINT "accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "auth_sessions" ADD CONSTRAINT "auth_sessions_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "party_members" ADD CONSTRAINT "party_members_party_id_fkey" FOREIGN KEY ("party_id") REFERENCES "public"."parties"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "party_members" ADD CONSTRAINT "party_members_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "ix_official_rulesets_game_slug" ON "official_rulesets" USING btree ("game_slug" text_ops);--> statement-breakpoint
CREATE INDEX "ix_official_rulesets_publisher_id" ON "official_rulesets" USING btree ("publisher_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_sessions_expires_at" ON "sessions" USING btree ("expires_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "ix_sessions_user_id" ON "sessions" USING btree ("user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_user_game_library_user_id" ON "user_game_library" USING btree ("user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_query_audit_log_created_at" ON "query_audit_log" USING btree ("created_at" timestamptz_ops);--> statement-breakpoint
CREATE INDEX "ix_query_audit_log_session_id" ON "query_audit_log" USING btree ("session_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_query_audit_log_user_id" ON "query_audit_log" USING btree ("user_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_ruleset_metadata_session_id" ON "ruleset_metadata" USING btree ("session_id" uuid_ops);--> statement-breakpoint
CREATE INDEX "ix_ruleset_metadata_status" ON "ruleset_metadata" USING btree ("status" text_ops);--> statement-breakpoint
CREATE INDEX "ix_ruleset_metadata_user_id" ON "ruleset_metadata" USING btree ("user_id" uuid_ops);
*/