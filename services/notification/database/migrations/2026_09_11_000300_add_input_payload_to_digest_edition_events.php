<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('digest_edition_events', function (Blueprint $table): void {
            $table->json('input_payload')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('digest_edition_events', function (Blueprint $table): void {
            $table->dropColumn('input_payload');
        });
    }
};
