<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        if (DB::getDriverName() === 'pgsql') {
            DB::statement('CREATE SCHEMA IF NOT EXISTS notify');
        }
    }

    public function down(): void
    {
        // The schema may contain durable delivery history; never drop it implicitly.
    }
};
