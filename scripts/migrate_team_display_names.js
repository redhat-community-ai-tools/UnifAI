/**
 * Migration: Fix team display_name in workflow_sessions.
 *
 * Finds all team sessions where display_name is stored as the team UUID
 * (instead of the human-readable name) and patches them using the team
 * name from the Identity database.
 *
 * Usage (local via podman):
 *   podman cp scripts/migrate_team_display_names.js <mongo_container>:/tmp/migrate_team_display_names.js
 *   podman exec <mongo_container> mongosh --eval "var DRY_RUN=true" /tmp/migrate_team_display_names.js
 *   podman exec <mongo_container> mongosh --eval "var DRY_RUN=false" /tmp/migrate_team_display_names.js
 *
 * Usage (OpenShift via oc):
 *   oc cp scripts/migrate_team_display_names.js <mongo_pod>:/tmp/migrate_team_display_names.js
 *   oc exec <mongo_pod> -- mongosh --eval "var DRY_RUN=true" /tmp/migrate_team_display_names.js
 *   oc exec <mongo_pod> -- mongosh --eval "var DRY_RUN=false" /tmp/migrate_team_display_names.js
 *
 * DRY_RUN=true  → only prints what WOULD be fixed (no writes)
 * DRY_RUN=false → actually patches the records
 *
 * Safe to run multiple times (idempotent).
 */

const dryRun = (typeof DRY_RUN !== "undefined") ? DRY_RUN : true;

print(dryRun ? "=== DRY RUN (no changes will be made) ===" : "=== LIVE RUN (will modify records) ===");
print("");

const sessionsDb = db.getSiblingDB("UnifAI");
const identityDb = db.getSiblingDB("users");

// Step 1: Build team_id → name lookup from Identity DB
const allTeams = identityDb.teams.find({}, { team_id: 1, name: 1, _id: 0 }).toArray();
const teamMap = {};
allTeams.forEach(t => { teamMap[t.team_id] = t.name; });

print(`Loaded ${allTeams.length} teams from Identity DB`);

// Step 2: Find all team sessions where display_name == team_id (broken records)
const broken = sessionsDb.workflow_sessions.aggregate([
    { $match: { "identity.type": "team", $expr: { $eq: ["$identity.display_name", "$identity.id"] } } },
    { $group: { _id: "$identity.id", count: { $sum: 1 } } }
]).toArray();

if (broken.length === 0) {
    print("\nNo broken records found. Nothing to do.");
    quit();
}

print(`\nFound ${broken.length} team(s) with UUID as display_name:\n`);

let totalFixed = 0;
let totalSkipped = 0;

// Step 3: For each broken team, look up real name and patch
broken.forEach(entry => {
    const teamId = entry._id;
    const count = entry.count;
    const realName = teamMap[teamId];

    if (!realName) {
        print(`  SKIP: ${teamId} (${count} sessions) — team not found in Identity DB`);
        totalSkipped += count;
        return;
    }

    if (dryRun) {
        print(`  WOULD FIX: ${teamId} → "${realName}" (${count} sessions)`);
        totalFixed += count;
    } else {
        const result = sessionsDb.workflow_sessions.updateMany(
            {
                "identity.type": "team",
                "identity.id": teamId,
                "identity.display_name": teamId
            },
            { $set: { "identity.display_name": realName } }
        );
        print(`  FIXED: ${teamId} → "${realName}" (${result.modifiedCount} sessions updated)`);
        totalFixed += result.modifiedCount;
    }
});

print(`\nDone. ${dryRun ? "Would fix" : "Fixed"}: ${totalFixed}, Skipped: ${totalSkipped}`);
if (dryRun) {
    print("\nTo apply changes, re-run with DRY_RUN=false");
}
