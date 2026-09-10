<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('digest_preferences', function (Blueprint $table): void {
            $table->uuid('subscriber_id')->primary();
            $table->boolean('enabled')->default(false);
            $table->unsignedBigInteger('revision')->default(1);
            $table->timestampTz('effective_from');
            $table->timestampsTz();
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
        });

        Schema::create('digest_preference_topics', function (Blueprint $table): void {
            $table->uuid('subscriber_id');
            $table->string('topic', 32);
            $table->primary(['subscriber_id', 'topic']);
            $table->foreign('subscriber_id')->references('subscriber_id')->on('digest_preferences')->cascadeOnDelete();
        });

        Schema::create('digest_editions', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('topic', 32);
            $table->timestampTz('window_start');
            $table->timestampTz('window_end');
            $table->timestampTz('cutoff_at');
            $table->timestampTz('deadline_at');
            $table->enum('status', ['frozen', 'generating', 'published', 'no_content', 'failed', 'invalidated']);
            $table->string('input_hash', 64)->nullable();
            $table->unsignedSmallInteger('input_count')->default(0);
            $table->boolean('coverage_truncated')->default(false);
            $table->string('prompt_version')->nullable();
            $table->string('model_provider')->nullable();
            $table->string('model_name')->nullable();
            $table->unsignedSmallInteger('generation_attempt_count')->default(0);
            $table->string('error_code')->nullable();
            $table->timestampTz('published_at')->nullable();
            $table->timestampTz('invalidated_at')->nullable();
            $table->string('invalidation_kind')->nullable();
            $table->string('invalidation_reason', 500)->nullable();
            $table->timestampsTz();
            $table->unique(['topic', 'window_start']);
            $table->index(['status', 'deadline_at']);
        });

        Schema::create('digest_edition_events', function (Blueprint $table): void {
            $table->uuid('edition_id');
            $table->uuid('public_event_id');
            $table->uuid('upstream_event_id');
            $table->unsignedSmallInteger('position');
            $table->primary(['edition_id', 'public_event_id']);
            $table->unique(['edition_id', 'upstream_event_id']);
            $table->foreign('edition_id')->references('id')->on('digest_editions')->cascadeOnDelete();
        });

        Schema::create('digest_translations', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('edition_id');
            $table->string('language', 16);
            $table->string('title', 300);
            $table->text('overview');
            $table->json('developments');
            $table->string('source_content_hash', 64);
            $table->timestampsTz();
            $table->foreign('edition_id')->references('id')->on('digest_editions')->cascadeOnDelete();
            $table->unique(['edition_id', 'language']);
        });

        Schema::create('digest_batches', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('subscriber_id');
            $table->uuid('channel_id');
            $table->timestampTz('window_start');
            $table->unsignedBigInteger('preference_revision');
            $table->unsignedBigInteger('channel_revision');
            $table->string('content_language', 16);
            $table->enum('status', ['pending', 'sending', 'sent', 'retry', 'no_content', 'failed', 'canceled', 'expired']);
            $table->unsignedSmallInteger('attempt_count')->default(0);
            $table->timestampTz('not_before');
            $table->timestampTz('deadline_at');
            $table->timestampTz('last_attempt_at')->nullable();
            $table->timestampTz('sent_at')->nullable();
            $table->string('provider_message_id')->nullable();
            $table->string('error_code')->nullable();
            $table->timestampsTz();
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
            $table->foreign('channel_id')->references('id')->on('channels')->cascadeOnDelete();
            $table->unique(['subscriber_id', 'window_start']);
            $table->index(['status', 'not_before']);
        });

        Schema::create('digest_batch_editions', function (Blueprint $table): void {
            $table->uuid('batch_id');
            $table->uuid('edition_id');
            $table->primary(['batch_id', 'edition_id']);
            $table->foreign('batch_id')->references('id')->on('digest_batches')->cascadeOnDelete();
            $table->foreign('edition_id')->references('id')->on('digest_editions')->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('digest_batch_editions');
        Schema::dropIfExists('digest_batches');
        Schema::dropIfExists('digest_translations');
        Schema::dropIfExists('digest_edition_events');
        Schema::dropIfExists('digest_editions');
        Schema::dropIfExists('digest_preference_topics');
        Schema::dropIfExists('digest_preferences');
    }
};
