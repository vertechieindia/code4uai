package ai.code4u.plugin.completion

import ai.code4u.plugin.client.Code4uClient
import ai.code4u.plugin.client.CompletionRequest
import ai.code4u.plugin.client.ContextFile
import ai.code4u.plugin.settings.Code4uSettings
import com.intellij.codeInsight.completion.*
import com.intellij.codeInsight.lookup.LookupElementBuilder
import com.intellij.icons.AllIcons
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.patterns.PlatformPatterns
import com.intellij.psi.PsiFile
import com.intellij.util.ProcessingContext
import kotlinx.coroutines.*
import javax.swing.Icon

/**
 * Provides AI-powered code completions from code4u.ai
 */
class Code4uCompletionContributor : CompletionContributor() {
    
    private val client = Code4uClient()
    private val settings = Code4uSettings.instance
    
    init {
        extend(
            CompletionType.BASIC,
            PlatformPatterns.psiElement(),
            Code4uCompletionProvider()
        )
    }
    
    inner class Code4uCompletionProvider : CompletionProvider<CompletionParameters>() {
        
        override fun addCompletions(
            parameters: CompletionParameters,
            context: ProcessingContext,
            result: CompletionResultSet
        ) {
            if (!settings.autocompleteEnabled) return
            
            val file = parameters.originalFile
            val editor = parameters.editor
            val offset = parameters.offset
            val document = editor.document
            
            val cursorLine = document.getLineNumber(offset)
            val lineStartOffset = document.getLineStartOffset(cursorLine)
            val cursorColumn = offset - lineStartOffset
            
            val filePath = file.virtualFile?.path ?: return
            val content = document.text
            val language = getLanguageId(file)
            
            // Get context from recently opened files
            val contextFiles = getContextFiles(parameters.editor.project, file.virtualFile)
            
            val request = CompletionRequest(
                file_path = filePath,
                content = content,
                cursor_line = cursorLine,
                cursor_column = cursorColumn,
                language = language,
                context_files = contextFiles
            )
            
            // Run completion request in background
            runBlocking {
                withContext(Dispatchers.IO) {
                    try {
                        val response = client.getCompletions(request)
                        response?.completions?.forEach { completion ->
                            val element = LookupElementBuilder.create(completion.text)
                                .withPresentableText(completion.display_text)
                                .withTypeText("code4u", true)
                                .withIcon(getIconForType(completion.type))
                                .withTailText(if (completion.documentation != null) " ..." else "", true)
                                .withInsertHandler { ctx, _ ->
                                    // Handle any post-insert actions
                                    if (settings.debugMode) {
                                        println("[code4u] Inserted: ${completion.text}")
                                    }
                                }
                            
                            // Add with priority based on score
                            val priority = (completion.score * 1000).toDouble()
                            result.addElement(PrioritizedLookupElement.withPriority(element, priority))
                        }
                    } catch (e: Exception) {
                        if (settings.debugMode) {
                            println("[code4u] Completion error: ${e.message}")
                        }
                    }
                }
            }
        }
        
        private fun getLanguageId(file: PsiFile): String {
            return when (file.language.id.lowercase()) {
                "kotlin" -> "kotlin"
                "java" -> "java"
                "python" -> "python"
                "javascript" -> "javascript"
                "typescript" -> "typescript"
                "rust" -> "rust"
                "go" -> "go"
                "c" -> "c"
                "c++" -> "cpp"
                "ruby" -> "ruby"
                "php" -> "php"
                "swift" -> "swift"
                "scala" -> "scala"
                else -> file.language.id.lowercase()
            }
        }
        
        private fun getContextFiles(project: Project?, excludeFile: VirtualFile?): List<ContextFile> {
            if (project == null) return emptyList()
            
            val contextFiles = mutableListOf<ContextFile>()
            val fileEditorManager = FileEditorManager.getInstance(project)
            
            // Get recently opened files
            fileEditorManager.openFiles
                .filter { it != excludeFile && it.length < 100_000 } // Exclude current and large files
                .take(5) // Limit context files
                .forEach { file ->
                    try {
                        val content = String(file.contentsToByteArray())
                        contextFiles.add(ContextFile(file.path, content))
                    } catch (e: Exception) {
                        // Skip files that can't be read
                    }
                }
            
            return contextFiles
        }
        
        private fun getIconForType(type: String): Icon {
            return when (type) {
                "function", "method" -> AllIcons.Nodes.Method
                "class" -> AllIcons.Nodes.Class
                "variable" -> AllIcons.Nodes.Variable
                "property" -> AllIcons.Nodes.Property
                "interface" -> AllIcons.Nodes.Interface
                "module" -> AllIcons.Nodes.Module
                "enum" -> AllIcons.Nodes.Enum
                "snippet" -> AllIcons.Nodes.Template
                else -> AllIcons.Nodes.Unknown
            }
        }
    }
}

