package ai.code4u.plugin.client

import ai.code4u.plugin.settings.Code4uSettings
import com.google.gson.Gson
import com.google.gson.JsonObject
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Client for communicating with code4u.ai backend API
 */
class Code4uClient {
    private val gson = Gson()
    private val settings = Code4uSettings.instance
    
    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()
    
    private val sseClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.SECONDS) // No timeout for SSE
        .build()

    val baseUrl: String
        get() = settings.serverUrl.ifBlank { "http://localhost:8002" }

    /**
     * Request autocomplete suggestions
     */
    fun getCompletions(request: CompletionRequest): CompletionResponse? {
        val json = gson.toJson(request)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/autocomplete/complete")
            .addHeader("Authorization", "Bearer ${settings.apiKey}")
            .addHeader("X-Tenant-ID", settings.tenantId)
            .post(body)
            .build()
        
        return try {
            client.newCall(httpRequest).execute().use { response ->
                if (response.isSuccessful) {
                    response.body?.string()?.let { 
                        gson.fromJson(it, CompletionResponse::class.java) 
                    }
                } else null
            }
        } catch (e: IOException) {
            null
        }
    }

    /**
     * Request inline completion (Tab)
     */
    fun getInlineCompletion(request: InlineCompletionRequest): InlineCompletionResponse? {
        val json = gson.toJson(request)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/autocomplete/inline")
            .addHeader("Authorization", "Bearer ${settings.apiKey}")
            .addHeader("X-Tenant-ID", settings.tenantId)
            .post(body)
            .build()
        
        return try {
            client.newCall(httpRequest).execute().use { response ->
                if (response.isSuccessful) {
                    response.body?.string()?.let { 
                        gson.fromJson(it, InlineCompletionResponse::class.java) 
                    }
                } else null
            }
        } catch (e: IOException) {
            null
        }
    }

    /**
     * Execute refactoring with streaming response
     */
    fun executeRefactor(
        request: RefactorRequest,
        onEvent: (RefactorEvent) -> Unit,
        onComplete: () -> Unit,
        onError: (String) -> Unit
    ): EventSource {
        val json = gson.toJson(request)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/agent/refactor/stream")
            .addHeader("Authorization", "Bearer ${settings.apiKey}")
            .addHeader("X-Tenant-ID", settings.tenantId)
            .addHeader("Accept", "text/event-stream")
            .post(body)
            .build()
        
        val listener = object : EventSourceListener() {
            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                try {
                    val event = gson.fromJson(data, RefactorEvent::class.java)
                    onEvent(event)
                } catch (e: Exception) {
                    // Ignore parse errors for non-JSON events
                }
            }
            
            override fun onClosed(eventSource: EventSource) {
                onComplete()
            }
            
            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                onError(t?.message ?: "Connection failed")
            }
        }
        
        return EventSources.createFactory(sseClient)
            .newEventSource(httpRequest, listener)
    }

    /**
     * Analyze impact of changes
     */
    fun analyzeImpact(request: ImpactRequest): ImpactResponse? {
        val json = gson.toJson(request)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/graph/impact")
            .addHeader("Authorization", "Bearer ${settings.apiKey}")
            .addHeader("X-Tenant-ID", settings.tenantId)
            .post(body)
            .build()
        
        return try {
            client.newCall(httpRequest).execute().use { response ->
                if (response.isSuccessful) {
                    response.body?.string()?.let { 
                        gson.fromJson(it, ImpactResponse::class.java) 
                    }
                } else null
            }
        } catch (e: IOException) {
            null
        }
    }

    /**
     * Chat with agent
     */
    fun chat(
        request: ChatRequest,
        onMessage: (ChatMessage) -> Unit,
        onComplete: () -> Unit,
        onError: (String) -> Unit
    ): EventSource {
        val json = gson.toJson(request)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/agent/chat/stream")
            .addHeader("Authorization", "Bearer ${settings.apiKey}")
            .addHeader("X-Tenant-ID", settings.tenantId)
            .addHeader("Accept", "text/event-stream")
            .post(body)
            .build()
        
        val listener = object : EventSourceListener() {
            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                try {
                    val message = gson.fromJson(data, ChatMessage::class.java)
                    onMessage(message)
                } catch (e: Exception) {
                    // Ignore parse errors
                }
            }
            
            override fun onClosed(eventSource: EventSource) {
                onComplete()
            }
            
            override fun onFailure(eventSource: EventSource, t: Throwable?, response: Response?) {
                onError(t?.message ?: "Connection failed")
            }
        }
        
        return EventSources.createFactory(sseClient)
            .newEventSource(httpRequest, listener)
    }

    /**
     * Test connection to server
     */
    fun testConnection(): Boolean {
        val httpRequest = Request.Builder()
            .url("$baseUrl/health")
            .get()
            .build()
        
        return try {
            client.newCall(httpRequest).execute().use { it.isSuccessful }
        } catch (e: IOException) {
            false
        }
    }
}

// Request/Response Data Classes
data class CompletionRequest(
    val file_path: String,
    val content: String,
    val cursor_line: Int,
    val cursor_column: Int,
    val language: String,
    val context_files: List<ContextFile> = emptyList()
)

data class ContextFile(
    val path: String,
    val content: String
)

data class CompletionResponse(
    val completions: List<Completion>,
    val cache_hit: Boolean = false
)

data class Completion(
    val text: String,
    val display_text: String,
    val type: String,
    val score: Float,
    val documentation: String? = null
)

data class InlineCompletionRequest(
    val file_path: String,
    val content: String,
    val cursor_line: Int,
    val cursor_column: Int,
    val language: String,
    val prefix: String,
    val suffix: String
)

data class InlineCompletionResponse(
    val suggestion: String?,
    val multi_line: Boolean = false,
    val confidence: Float = 0f
)

data class RefactorRequest(
    val intent: String,
    val file_path: String,
    val selection: String? = null,
    val selection_start: Position? = null,
    val selection_end: Position? = null,
    val workspace_id: String
)

data class Position(
    val line: Int,
    val column: Int
)

data class RefactorEvent(
    val type: String, // state_change, diff, error, complete
    val state: String? = null,
    val message: String? = null,
    val diff: DiffPayload? = null
)

data class DiffPayload(
    val file_path: String,
    val original: String,
    val modified: String,
    val hunks: List<DiffHunk>
)

data class DiffHunk(
    val start_line: Int,
    val end_line: Int,
    val content: String
)

data class ImpactRequest(
    val file_path: String,
    val symbol: String? = null
)

data class ImpactResponse(
    val impacted_files: List<String>,
    val impacted_symbols: List<String>,
    val breaking_changes: Boolean,
    val risk_level: String
)

data class ChatRequest(
    val message: String,
    val conversation_id: String? = null,
    val context: ChatContext? = null
)

data class ChatContext(
    val file_path: String? = null,
    val selection: String? = null,
    val language: String? = null
)

data class ChatMessage(
    val role: String, // user, assistant, system
    val content: String,
    val timestamp: Long? = null
)

