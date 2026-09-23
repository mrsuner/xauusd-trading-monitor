<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        if (DB::getDriverName() === 'pgsql') {
            // Production pre-provisions this schema with the restricted role as
            // owner. PostgreSQL checks database CREATE privilege even for
            // CREATE SCHEMA IF NOT EXISTS, so avoid issuing it when it exists.
            $schemaCount = (int) DB::scalar(
                "SELECT count(*) FROM pg_namespace WHERE nspname = 'notify'"
            );

            if ($schemaCount === 0) {
                DB::statement('CREATE SCHEMA notify');
            }
        }
    }

    public function down(): void
    {
        // The schema may contain durable delivery history; never drop it implicitly.
    }
};
