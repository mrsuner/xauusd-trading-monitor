<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        if (DB::getDriverName() === 'pgsql') {
            DB::statement('ALTER TABLE channels DROP CONSTRAINT channels_type_check');
            DB::statement("ALTER TABLE channels ADD CONSTRAINT channels_type_check CHECK (type IN ('telegram', 'push'))");

            return;
        }

        Schema::table('channels', function (Blueprint $table): void {
            $table->enum('type', ['telegram', 'push'])->change();
        });
    }

    public function down(): void
    {
        if (DB::table('channels')->where('type', 'push')->exists()) {
            throw new RuntimeException('Disable and remove push channels before rolling back this migration.');
        }

        if (DB::getDriverName() === 'pgsql') {
            DB::statement('ALTER TABLE channels DROP CONSTRAINT channels_type_check');
            DB::statement("ALTER TABLE channels ADD CONSTRAINT channels_type_check CHECK (type IN ('telegram'))");

            return;
        }

        Schema::table('channels', function (Blueprint $table): void {
            $table->enum('type', ['telegram'])->change();
        });
    }
};
