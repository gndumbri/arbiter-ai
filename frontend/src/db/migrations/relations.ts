import { relations } from "drizzle-orm/relations";
import { users, parties, savedRulings, subscriptions, fileBlocklist, publishers, officialRulesets, sessions, userGameLibrary, queryAuditLog, rulesetMetadata, accounts, authSessions, partyMembers } from "./schema";

export const partiesRelations = relations(parties, ({one, many}) => ({
	user: one(users, {
		fields: [parties.ownerId],
		references: [users.id]
	}),
	partyMembers: many(partyMembers),
}));

export const usersRelations = relations(users, ({many}) => ({
	parties: many(parties),
	savedRulings: many(savedRulings),
	subscriptions: many(subscriptions),
	fileBlocklists: many(fileBlocklist),
	sessions: many(sessions),
	userGameLibraries: many(userGameLibrary),
	queryAuditLogs: many(queryAuditLog),
	rulesetMetadata: many(rulesetMetadata),
	accounts: many(accounts),
	authSessions: many(authSessions),
	partyMembers: many(partyMembers),
}));

export const savedRulingsRelations = relations(savedRulings, ({one}) => ({
	user: one(users, {
		fields: [savedRulings.userId],
		references: [users.id]
	}),
}));

export const subscriptionsRelations = relations(subscriptions, ({one}) => ({
	user: one(users, {
		fields: [subscriptions.userId],
		references: [users.id]
	}),
}));

export const fileBlocklistRelations = relations(fileBlocklist, ({one}) => ({
	user: one(users, {
		fields: [fileBlocklist.reportedBy],
		references: [users.id]
	}),
}));

export const officialRulesetsRelations = relations(officialRulesets, ({one}) => ({
	publisher: one(publishers, {
		fields: [officialRulesets.publisherId],
		references: [publishers.id]
	}),
}));

export const publishersRelations = relations(publishers, ({many}) => ({
	officialRulesets: many(officialRulesets),
}));

export const sessionsRelations = relations(sessions, ({one, many}) => ({
	user: one(users, {
		fields: [sessions.userId],
		references: [users.id]
	}),
	queryAuditLogs: many(queryAuditLog),
	rulesetMetadata: many(rulesetMetadata),
}));

export const userGameLibraryRelations = relations(userGameLibrary, ({one}) => ({
	user: one(users, {
		fields: [userGameLibrary.userId],
		references: [users.id]
	}),
}));

export const queryAuditLogRelations = relations(queryAuditLog, ({one}) => ({
	session: one(sessions, {
		fields: [queryAuditLog.sessionId],
		references: [sessions.id]
	}),
	user: one(users, {
		fields: [queryAuditLog.userId],
		references: [users.id]
	}),
}));

export const rulesetMetadataRelations = relations(rulesetMetadata, ({one}) => ({
	session: one(sessions, {
		fields: [rulesetMetadata.sessionId],
		references: [sessions.id]
	}),
	user: one(users, {
		fields: [rulesetMetadata.userId],
		references: [users.id]
	}),
}));

export const accountsRelations = relations(accounts, ({one}) => ({
	user: one(users, {
		fields: [accounts.userId],
		references: [users.id]
	}),
}));

export const authSessionsRelations = relations(authSessions, ({one}) => ({
	user: one(users, {
		fields: [authSessions.userId],
		references: [users.id]
	}),
}));

export const partyMembersRelations = relations(partyMembers, ({one}) => ({
	party: one(parties, {
		fields: [partyMembers.partyId],
		references: [parties.id]
	}),
	user: one(users, {
		fields: [partyMembers.userId],
		references: [users.id]
	}),
}));