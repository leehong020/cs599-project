"""初始化应用数据库结构。

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-09

这版迁移对应阶段 1 的“空库可迁移”验收，同时提前落下阶段 0
冻结过的核心事实表。后续阶段会逐步为这些表补 ORM model、
repository 和 service，但事实来源从一开始就保持一致。
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 用户基础身份表只保存账号级信息。时区、默认日历等确定性偏好
    # 放在 user_settings，避免 users 表同时承担身份和业务配置两种职责。
    op.create_table(
        "users",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # user_settings 是完整性校验依赖的事实来源。长期记忆可以保存偏好候选，
    # 但不能替代这些确定性配置。
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("timezone", sa.Text()),
        sa.Column("default_calendar_id", sa.Text()),
        sa.Column("default_signature_id", sa.Text()),
        sa.Column("default_sender_email", sa.Text()),
        sa.Column("default_meeting_duration_minutes", sa.Integer()),
        sa.Column("meeting_buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("working_hours_json", sa.Text()),
        sa.Column("lunch_break_json", sa.Text()),
        sa.Column("email_tone_internal", sa.Text()),
        sa.Column("email_tone_external", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # OAuth Token 后续必须由 OAuth service 加密保存。阶段 1 先落表结构，
    # 让阶段 2 可以专注实现授权流程本身。
    op.create_table(
        "oauth_credentials",
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("encrypted_access_token", sa.Text()),
        sa.Column("encrypted_refresh_token", sa.Text()),
        sa.Column("expires_at", sa.Text()),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # 署名是用户显式控制的内容。如果当前表和本轮对话都没有提供署名，
    # 助理不得凭空生成。
    op.create_table(
        "signatures",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # 联系人表支持收件人和参会人的唯一匹配。重名或歧义必须由策略代码追问，
    # 不能静默选择其中一个。
    op.create_table(
        "contacts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text()),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_contacts_user_name", "contacts", ["user_id", "display_name"])
    # Thread 表示用户可见的一段对话。Work Item 和 Proposal 挂在 Thread 下，
    # 这样刷新页面或服务重启后可以恢复多轮状态。
    op.create_table(
        "threads",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # Messages 用 JSON 保存对话记录，让普通文本、卡片和未来结构化事件
    # 可以共用一条追加式时间线。
    op.create_table(
        "messages",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_messages_thread_created_at", "messages", ["thread_id", "created_at"])
    # Work Item 是未完成用户意图的持久化单位。同一个聊天 Thread 可以同时
    # 存在多个打开事项，例如一封暂缓邮件和一个正在准备的日程草稿。
    op.create_table(
        "work_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("work_item_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("maturity", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_work_items_thread_status", "work_items", ["thread_id", "status"])
    # Artifact 保存本地草稿和只读结果。草稿生成只写本地；写 Gmail Draft
    # 或 Calendar Event 必须走后续 Proposal + Authorization 路径。
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("work_item_id", sa.Text(), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("artifact_type", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # Field Evidence 解释每个关键字段从哪里来。必填字段缺失、歧义，
    # 或仅来自不允许的推断时，Completeness Gate 必须拒绝可执行 Proposal。
    op.create_table(
        "field_evidence",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("artifact_id", sa.Text(), sa.ForeignKey("artifacts.id"), nullable=False),
        sa.Column("field_path", sa.Text(), nullable=False),
        sa.Column("value_json", sa.Text()),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("confirmation_status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_field_evidence_artifact", "field_evidence", ["artifact_id", "field_path"])
    # Proposal Group 允许一个用户请求产生多个可确认动作，例如先创建会议，
    # 再把会议链接写入邮件并发送。
    op.create_table(
        "proposal_groups",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # Proposal Item 是展示给用户确认的精确 payload。version 和 fingerprint
    # 用于保证草稿变化后旧授权立即失效。
    op.create_table(
        "proposal_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("proposal_group_id", sa.Text(), sa.ForeignKey("proposal_groups.id"), nullable=False),
        sa.Column("work_item_id", sa.Text(), sa.ForeignKey("work_items.id"), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_proposal_items_group", "proposal_items", ["proposal_group_id"])
    op.create_index("idx_proposal_items_work_item", "proposal_items", ["work_item_id", "status"])
    # Authorization 记录用户对某个 Proposal 版本的决定。Execution Service
    # 在任何外部写操作前都必须校验这些记录。
    op.create_table(
        "action_authorizations",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("proposal_item_id", sa.Text(), sa.ForeignKey("proposal_items.id"), nullable=False),
        sa.Column("proposal_version", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("user_message_id", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    # Action Event 是外部调用的恢复账本。它保存幂等 key 和外部资源 ID，
    # 防止重复点击或崩溃恢复时静默重复发送邮件、重复创建日程。
    op.create_table(
        "action_events",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("proposal_item_id", sa.Text(), sa.ForeignKey("proposal_items.id")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("external_provider", sa.Text()),
        sa.Column("external_resource_id", sa.Text()),
        sa.Column("payload_json", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index(
        "idx_action_events_idempotency",
        "action_events",
        ["idempotency_key"],
        unique=True,
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )
    # uploaded_files 只保存上传文件元数据，与解析文本分离。这样文件归属、
    # 删除和去重规则都能保持清晰。
    op.create_table(
        "uploaded_files",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("thread_id", sa.Text(), sa.ForeignKey("threads.id")),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_uploaded_files_thread", "uploaded_files", ["thread_id", "created_at"])
    # file_extractions 保存不可信的文件解析结果。它们可以支持摘要和草稿，
    # 但 Prompt Injection 规则禁止它们批准动作或覆盖系统策略。
    op.create_table(
        "file_extractions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("uploaded_file_id", sa.Text(), sa.ForeignKey("uploaded_files.id"), nullable=False),
        sa.Column("extractor_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("text_content", sa.Text()),
        sa.Column("metadata_json", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )
    # selected_context_refs 记录用户本轮显式选中的对象。后端指代解析应优先
    # 使用它，而不是模糊的“最近展示”；但它只在当前用户和 Thread 内有效。
    op.create_table(
        "selected_context_refs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("thread_id", sa.Text(), sa.ForeignKey("threads.id"), nullable=False),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", sa.Text(), sa.ForeignKey("messages.id")),
        sa.Column("ref_type", sa.Text(), nullable=False),
        sa.Column("ref_id", sa.Text(), nullable=False),
        sa.Column("selection_json", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("idx_selected_context_message", "selected_context_refs", ["message_id"])
    # memories 保存长期偏好候选或已激活记忆。时区、默认日历等确定性配置
    # 仍以 user_settings 为准。
    op.create_table(
        "memories",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("namespace", sa.Text(), nullable=False),
        sa.Column("memory_key", sa.Text(), nullable=False),
        sa.Column("memory_type", sa.Text(), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_thread_id", sa.Text()),
        sa.Column("source_message_id", sa.Text()),
        sa.Column("expires_at", sa.Text()),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    # 回滚顺序必须和外键依赖相反：先删除依赖其他表的记录表，
    # 再删除基础身份和设置表。
    op.drop_table("memories")
    op.drop_index("idx_selected_context_message", table_name="selected_context_refs")
    op.drop_table("selected_context_refs")
    op.drop_table("file_extractions")
    op.drop_index("idx_uploaded_files_thread", table_name="uploaded_files")
    op.drop_table("uploaded_files")
    op.drop_index("idx_action_events_idempotency", table_name="action_events")
    op.drop_table("action_events")
    op.drop_table("action_authorizations")
    op.drop_index("idx_proposal_items_work_item", table_name="proposal_items")
    op.drop_index("idx_proposal_items_group", table_name="proposal_items")
    op.drop_table("proposal_items")
    op.drop_table("proposal_groups")
    op.drop_index("idx_field_evidence_artifact", table_name="field_evidence")
    op.drop_table("field_evidence")
    op.drop_table("artifacts")
    op.drop_index("idx_work_items_thread_status", table_name="work_items")
    op.drop_table("work_items")
    op.drop_index("idx_messages_thread_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_table("threads")
    op.drop_index("idx_contacts_user_name", table_name="contacts")
    op.drop_table("contacts")
    op.drop_table("signatures")
    op.drop_table("oauth_credentials")
    op.drop_table("user_settings")
    op.drop_table("users")
