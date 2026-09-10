<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('subscribers', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->string('account_user_id')->unique();
            $table->boolean('master_enabled')->default(false);
            $table->boolean('match_all_categories')->default(false);
            $table->enum('min_severity', ['S', 'A', 'B', 'C'])->default('A');
            $table->string('content_language', 16)->default('zh-Hant');
            $table->unsignedBigInteger('revision')->default(1);
            $table->timestampTz('effective_from');
            $table->timestampsTz();
        });

        Schema::create('category_subscriptions', function (Blueprint $table): void {
            $table->uuid('subscriber_id');
            $table->string('key');
            $table->primary(['subscriber_id', 'key']);
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
        });

        Schema::create('tag_subscriptions', function (Blueprint $table): void {
            $table->uuid('subscriber_id');
            $table->string('key');
            $table->primary(['subscriber_id', 'key']);
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
        });

        Schema::create('channels', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('subscriber_id');
            $table->enum('type', ['telegram']);
            $table->boolean('enabled')->default(false);
            $table->boolean('verified')->default(false);
            $table->unsignedBigInteger('revision')->default(1);
            $table->timestampTz('enabled_from')->nullable();
            $table->text('encrypted_target')->nullable();
            $table->string('target_fingerprint', 64)->nullable();
            $table->string('target_hint')->nullable();
            $table->string('link_code_hash', 64)->nullable()->unique();
            $table->timestampTz('link_expires_at')->nullable();
            $table->timestampTz('linked_at')->nullable();
            $table->string('last_error_code')->nullable();
            $table->timestampsTz();
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
            $table->unique(['subscriber_id', 'type']);
            $table->unique(['type', 'target_fingerprint']);
        });

        Schema::create('event_receipts', function (Blueprint $table): void {
            $table->uuid('upstream_event_id')->primary();
            $table->uuid('public_event_id')->nullable();
            $table->timestampTz('received_at');
            $table->timestampTz('processed_at')->nullable();
            $table->timestampTz('expires_at')->index();
            $table->timestampsTz();
        });

        Schema::create('deliveries', function (Blueprint $table): void {
            $table->uuid('id')->primary();
            $table->uuid('subscriber_id');
            $table->uuid('channel_id');
            $table->uuid('upstream_event_id');
            $table->uuid('public_event_id');
            $table->string('channel_type', 24);
            $table->enum('priority', ['high', 'standard'])->default('standard');
            $table->unsignedBigInteger('subscriber_revision');
            $table->unsignedBigInteger('channel_revision');
            $table->enum('status', ['pending', 'sending', 'sent', 'retry', 'failed', 'canceled', 'expired'])->default('pending');
            $table->unsignedSmallInteger('attempt_count')->default(0);
            $table->timestampTz('not_before');
            $table->timestampTz('dispatch_requested_at')->nullable();
            $table->timestampTz('dispatch_confirmed_at')->nullable();
            $table->timestampTz('last_attempt_at')->nullable();
            $table->timestampTz('expires_at');
            $table->timestampTz('sent_at')->nullable();
            $table->string('provider_message_id')->nullable();
            $table->string('error_code')->nullable();
            $table->timestampsTz();
            $table->foreign('subscriber_id')->references('id')->on('subscribers')->cascadeOnDelete();
            $table->foreign('channel_id')->references('id')->on('channels')->cascadeOnDelete();
            $table->unique(['subscriber_id', 'upstream_event_id', 'channel_type']);
            $table->index(['status', 'not_before', 'dispatch_requested_at']);
        });

        Schema::create('runtime_state', function (Blueprint $table): void {
            $table->string('key')->primary();
            $table->json('value');
            $table->timestampsTz();
        });

        Schema::create('failed_jobs', function (Blueprint $table): void {
            $table->id();
            $table->string('uuid')->unique();
            $table->text('connection');
            $table->text('queue');
            $table->longText('payload');
            $table->longText('exception');
            $table->timestamp('failed_at')->useCurrent();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('failed_jobs');
        Schema::dropIfExists('runtime_state');
        Schema::dropIfExists('deliveries');
        Schema::dropIfExists('event_receipts');
        Schema::dropIfExists('channels');
        Schema::dropIfExists('tag_subscriptions');
        Schema::dropIfExists('category_subscriptions');
        Schema::dropIfExists('subscribers');
    }
};
