import { pgTable, varchar, foreignKey, uuid, timestamp, text, json, unique, boolean, index, integer, doublePrecision, primaryKey } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"



export const alembicVersion = pgTable("alembic_version", {
	versionNum: varchar("version_num", { length: 32 }).primaryKey().notNull(),
});

export const parties = pgTable("parties", {
	id: uuid().primaryKey().notNull(),
	name: varchar().notNull(),
	ownerId: uuid("owner_id").notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.ownerId],
			foreignColumns: [users.id],
			name: "parties_owner_id_fkey"
		}).onDelete("cascade"),
]);

export const savedRulings = pgTable("saved_rulings", {
	id: uuid().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	query: text().notNull(),
	verdictJson: json("verdict_json").notNull(),
	privacyLevel: varchar("privacy_level").notNull(),
	tags: json(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "saved_rulings_user_id_fkey"
		}).onDelete("cascade"),
]);

export const subscriptions = pgTable("subscriptions", {
	id: uuid().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	stripeCustomerId: varchar("stripe_customer_id").notNull(),
	stripeSubscriptionId: varchar("stripe_subscription_id"),
	planTier: varchar("plan_tier").notNull(),
	status: varchar().notNull(),
	currentPeriodEnd: timestamp("current_period_end", { withTimezone: true, mode: 'string' }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "subscriptions_user_id_fkey"
		}).onDelete("cascade"),
	unique("subscriptions_user_id_key").on(table.userId),
	unique("subscriptions_stripe_customer_id_key").on(table.stripeCustomerId),
	unique("subscriptions_stripe_subscription_id_key").on(table.stripeSubscriptionId),
]);

export const users = pgTable("users", {
	id: uuid().primaryKey().notNull(),
	email: varchar().notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	name: varchar(),
	emailVerified: timestamp("email_verified", { withTimezone: true, mode: 'string' }),
	image: varchar(),
}, (table) => [
	unique("users_email_key").on(table.email),
]);

export const fileBlocklist = pgTable("file_blocklist", {
	hash: varchar().primaryKey().notNull(),
	reason: varchar().notNull(),
	reportedBy: uuid("reported_by"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.reportedBy],
			foreignColumns: [users.id],
			name: "file_blocklist_reported_by_fkey"
		}),
]);

export const publishers = pgTable("publishers", {
	id: uuid().primaryKey().notNull(),
	name: varchar().notNull(),
	slug: varchar().notNull(),
	apiKeyHash: varchar("api_key_hash").notNull(),
	contactEmail: varchar("contact_email").notNull(),
	verified: boolean().notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	unique("publishers_slug_key").on(table.slug),
]);

export const officialRulesets = pgTable("official_rulesets", {
	id: uuid().primaryKey().notNull(),
	publisherId: uuid("publisher_id").notNull(),
	gameName: varchar("game_name").notNull(),
	gameSlug: varchar("game_slug").notNull(),
	sourceType: varchar("source_type").notNull(),
	sourcePriority: integer("source_priority").notNull(),
	version: varchar().notNull(),
	chunkCount: integer("chunk_count").notNull(),
	status: varchar().notNull(),
	pineconeNamespace: varchar("pinecone_namespace").notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("ix_official_rulesets_game_slug").using("btree", table.gameSlug.asc().nullsLast().op("text_ops")),
	index("ix_official_rulesets_publisher_id").using("btree", table.publisherId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.publisherId],
			foreignColumns: [publishers.id],
			name: "official_rulesets_publisher_id_fkey"
		}).onDelete("cascade"),
]);

export const sessions = pgTable("sessions", {
	id: uuid().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	gameName: varchar("game_name").notNull(),
	activeRulesetIds: uuid("active_ruleset_ids").array(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	expiresAt: timestamp("expires_at", { withTimezone: true, mode: 'string' }).notNull(),
}, (table) => [
	index("ix_sessions_expires_at").using("btree", table.expiresAt.asc().nullsLast().op("timestamptz_ops")),
	index("ix_sessions_user_id").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "sessions_user_id_fkey"
		}).onDelete("cascade"),
]);

export const userGameLibrary = pgTable("user_game_library", {
	id: uuid().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	gameName: varchar("game_name").notNull(),
	officialRulesetIds: uuid("official_ruleset_ids").array(),
	personalRulesetIds: uuid("personal_ruleset_ids").array(),
	isFavorite: boolean("is_favorite").notNull(),
	lastQueried: timestamp("last_queried", { withTimezone: true, mode: 'string' }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("ix_user_game_library_user_id").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "user_game_library_user_id_fkey"
		}).onDelete("cascade"),
]);

export const queryAuditLog = pgTable("query_audit_log", {
	id: uuid().primaryKey().notNull(),
	sessionId: uuid("session_id"),
	userId: uuid("user_id"),
	queryText: text("query_text").notNull(),
	expandedQuery: text("expanded_query"),
	verdictSummary: text("verdict_summary"),
	reasoningChain: text("reasoning_chain"),
	confidence: doublePrecision(),
	confidenceReason: text("confidence_reason"),
	citationIds: varchar("citation_ids").array(),
	latencyMs: integer("latency_ms"),
	feedback: varchar(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("ix_query_audit_log_created_at").using("btree", table.createdAt.asc().nullsLast().op("timestamptz_ops")),
	index("ix_query_audit_log_session_id").using("btree", table.sessionId.asc().nullsLast().op("uuid_ops")),
	index("ix_query_audit_log_user_id").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.sessionId],
			foreignColumns: [sessions.id],
			name: "query_audit_log_session_id_fkey"
		}).onDelete("set null"),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "query_audit_log_user_id_fkey"
		}).onDelete("set null"),
]);

export const rulesetMetadata = pgTable("ruleset_metadata", {
	id: uuid().primaryKey().notNull(),
	sessionId: uuid("session_id").notNull(),
	userId: uuid("user_id").notNull(),
	filename: varchar().notNull(),
	gameName: varchar("game_name").notNull(),
	fileHash: varchar("file_hash").notNull(),
	sourceType: varchar("source_type").notNull(),
	sourcePriority: integer("source_priority").notNull(),
	chunkCount: integer("chunk_count").notNull(),
	status: varchar().notNull(),
	errorMessage: text("error_message"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("ix_ruleset_metadata_session_id").using("btree", table.sessionId.asc().nullsLast().op("uuid_ops")),
	index("ix_ruleset_metadata_status").using("btree", table.status.asc().nullsLast().op("text_ops")),
	index("ix_ruleset_metadata_user_id").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.sessionId],
			foreignColumns: [sessions.id],
			name: "ruleset_metadata_session_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "ruleset_metadata_user_id_fkey"
		}).onDelete("cascade"),
]);

export const accounts = pgTable("accounts", {
	id: uuid().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	type: varchar().notNull(),
	provider: varchar().notNull(),
	providerAccountId: varchar("provider_account_id").notNull(),
	refreshToken: text("refresh_token"),
	accessToken: text("access_token"),
	expiresAt: integer("expires_at"),
	tokenType: varchar("token_type"),
	scope: varchar(),
	idToken: text("id_token"),
	sessionState: varchar("session_state"),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "accounts_user_id_fkey"
		}).onDelete("cascade"),
	unique("uq_account_provider").on(table.provider, table.providerAccountId),
]);

export const authSessions = pgTable("auth_sessions", {
	id: uuid().primaryKey().notNull(),
	sessionToken: varchar("session_token").notNull(),
	userId: uuid("user_id").notNull(),
	expires: timestamp({ withTimezone: true, mode: 'string' }).notNull(),
}, (table) => [
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "auth_sessions_user_id_fkey"
		}).onDelete("cascade"),
	unique("auth_sessions_session_token_key").on(table.sessionToken),
]);

export const verificationTokens = pgTable("verification_tokens", {
	identifier: varchar().notNull(),
	token: varchar().notNull(),
	expires: timestamp({ withTimezone: true, mode: 'string' }).notNull(),
}, (table) => [
	primaryKey({ columns: [table.identifier, table.token], name: "verification_tokens_pkey"}),
	unique("verification_tokens_token_key").on(table.token),
]);

export const partyMembers = pgTable("party_members", {
	partyId: uuid("party_id").notNull(),
	userId: uuid("user_id").notNull(),
	role: varchar().notNull(),
	joinedAt: timestamp("joined_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	foreignKey({
			columns: [table.partyId],
			foreignColumns: [parties.id],
			name: "party_members_party_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [users.id],
			name: "party_members_user_id_fkey"
		}).onDelete("cascade"),
	primaryKey({ columns: [table.partyId, table.userId], name: "party_members_pkey"}),
]);
