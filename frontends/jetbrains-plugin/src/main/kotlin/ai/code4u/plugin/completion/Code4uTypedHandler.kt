package ai.code4u.plugin.completion

import ai.code4u.plugin.settings.Code4uSettings
import com.intellij.codeInsight.editorActions.TypedHandlerDelegate
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.psi.PsiFile

/**
 * Handles typed characters to trigger inline completions
 */
class Code4uTypedHandler : TypedHandlerDelegate() {
    
    private val settings = Code4uSettings.instance
    
    // Characters that should trigger completion
    private val triggerChars = setOf('.', '(', '{', '[', ':', ' ', '\n', ',', '=', '>')
    
    override fun charTyped(c: Char, project: Project, editor: Editor, file: PsiFile): Result {
        if (!settings.inlineCompletionEnabled) {
            return Result.CONTINUE
        }
        
        // Trigger inline completion on certain characters
        if (c in triggerChars) {
            // The inline completion provider will be automatically triggered
            // by IntelliJ's inline completion framework
        }
        
        return Result.CONTINUE
    }
}

