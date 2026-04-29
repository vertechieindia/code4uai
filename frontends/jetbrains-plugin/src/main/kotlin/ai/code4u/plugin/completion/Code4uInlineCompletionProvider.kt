package ai.code4u.plugin.completion

import ai.code4u.plugin.client.Code4uClient
import ai.code4u.plugin.client.InlineCompletionRequest
import ai.code4u.plugin.settings.Code4uSettings
import com.intellij.codeInsight.inline.completion.*
import com.intellij.codeInsight.inline.completion.elements.InlineCompletionElement
import com.intellij.codeInsight.inline.completion.elements.InlineCompletionGrayTextElement
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn

/**
 * Provides inline (ghost text) completions - Tab to accept
 * Similar to Cursor/Windsurf Tab completion
 */
class Code4uInlineCompletionProvider : InlineCompletionProvider {
    
    private val client = Code4uClient()
    private val settings = Code4uSettings.instance
    
    override val id: InlineCompletionProviderID
        get() = InlineCompletionProviderID("code4u.inline")
    
    override suspend fun getSuggestion(request: InlineCompletionRequest): InlineCompletionSuggestion {
        if (!settings.inlineCompletionEnabled) {
            return InlineCompletionSuggestion.Empty
        }
        
        val editor = request.editor
        val document = editor.document
        val offset = request.endOffset
        
        val cursorLine = document.getLineNumber(offset)
        val lineStartOffset = document.getLineStartOffset(cursorLine)
        val cursorColumn = offset - lineStartOffset
        
        val file = request.file
        val filePath = file.virtualFile?.path ?: return InlineCompletionSuggestion.Empty
        val content = document.text
        val language = getLanguageId(file)
        
        // Get prefix and suffix for context
        val prefix = content.substring(0, offset)
        val suffix = content.substring(offset)
        
        val apiRequest = ai.code4u.plugin.client.InlineCompletionRequest(
            file_path = filePath,
            content = content,
            cursor_line = cursorLine,
            cursor_column = cursorColumn,
            language = language,
            prefix = prefix.takeLast(2000), // Limit context size
            suffix = suffix.take(500)
        )
        
        return object : InlineCompletionSuggestion {
            override val suggestionFlow: Flow<InlineCompletionElement>
                get() = flow {
                    try {
                        val response = client.getInlineCompletion(apiRequest)
                        response?.suggestion?.let { suggestion ->
                            if (suggestion.isNotBlank()) {
                                emit(InlineCompletionGrayTextElement(suggestion))
                            }
                        }
                    } catch (e: Exception) {
                        if (settings.debugMode) {
                            println("[code4u] Inline completion error: ${e.message}")
                        }
                    }
                }.flowOn(Dispatchers.IO)
        }
    }
    
    override fun isEnabled(event: InlineCompletionEvent): Boolean {
        return settings.inlineCompletionEnabled
    }
    
    private fun getLanguageId(file: com.intellij.psi.PsiFile): String {
        return when (file.language.id.lowercase()) {
            "kotlin" -> "kotlin"
            "java" -> "java"
            "python" -> "python"
            "javascript" -> "javascript"
            "typescript" -> "typescript"
            else -> file.language.id.lowercase()
        }
    }
}

