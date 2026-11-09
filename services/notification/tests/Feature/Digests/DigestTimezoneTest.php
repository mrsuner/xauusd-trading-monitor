<?php

namespace Tests\Feature\Digests;

use App\Models\DigestEdition;
use Carbon\CarbonImmutable;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

class DigestTimezoneTest extends TestCase
{
    public function test_postgres_connections_use_utc(): void
    {
        $this->assertSame('UTC', config('database.connections.pgsql.timezone'));
    }

    public function test_deadlines_round_trip_on_a_non_utc_postgres_server(): void
    {
        $database = getenv('TICKBASE_TEST_PG_DATABASE');
        if (! $database) {
            $this->markTestSkipped('Set TICKBASE_TEST_PG_DATABASE to an isolated local QA database.');
        }
        $this->assertMatchesRegularExpression('/^tickbase_ios_qa_[0-9]+$/', $database);
        $connection = array_replace(config('database.connections.pgsql'), [
            'url' => null, 'database' => $database, 'search_path' => 'public',
        ]);
        config(['database.connections.digest_clock_test' => $connection]);
        $db = DB::connection('digest_clock_test');

        try {
            $this->assertSame('UTC', $db->selectOne('SHOW timezone')->TimeZone);
            $db->statement('CREATE TEMP TABLE qa_digest_clock (id uuid PRIMARY KEY, deadline_at timestamptz)');
            $deadline = CarbonImmutable::parse('2026-10-09 01:00:00 UTC');
            $now = $deadline->subMinutes(45);

            // Reproduce the old connection behavior before checking the fix.
            $db->statement("SET TIME ZONE 'Asia/Bangkok'");
            $old = new DigestEdition;
            $old->setConnection('digest_clock_test')->setTable('qa_digest_clock');
            $old->timestamps = false;
            $old->deadline_at = $deadline;
            $old->save();
            $old->refresh();
            $this->assertTrue($old->deadline_at->lessThan($now));
            $this->assertSame($deadline->subHours(7)->timestamp, $old->deadline_at->timestamp);

            $db->statement("SET TIME ZONE 'UTC'");
            $fixed = new DigestEdition;
            $fixed->setConnection('digest_clock_test')->setTable('qa_digest_clock');
            $fixed->timestamps = false;
            $fixed->deadline_at = $deadline;
            $fixed->save();
            $fixed->refresh();
            $this->assertSame($deadline->timestamp, $fixed->deadline_at->timestamp);
            $this->assertTrue($fixed->deadline_at->greaterThan($now));

            // The same timestamp binding must preserve the 168-hour deletion grace period.
            $fixed->deadline_at = $now->addHours(168);
            $fixed->save();
            $fixed->refresh();
            $this->assertSame(168 * 3600, $fixed->deadline_at->timestamp - $now->timestamp);
        } finally {
            DB::purge('digest_clock_test');
        }
    }
}
