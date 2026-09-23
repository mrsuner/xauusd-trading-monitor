<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('digest_editions', function (Blueprint $table): void {
            $table->unsignedInteger('model_prompt_tokens')->default(0);
            $table->unsignedInteger('model_completion_tokens')->default(0);
            $table->unsignedInteger('model_latency_ms')->default(0);
            $table->json('model_request_ids')->nullable();
        });
    }

    public function down(): void
    {
        Schema::table('digest_editions', function (Blueprint $table): void {
            $table->dropColumn([
                'model_prompt_tokens',
                'model_completion_tokens',
                'model_latency_ms',
                'model_request_ids',
            ]);
        });
    }
};
