package ai.code4u.plugin.actions

import ai.code4u.plugin.client.Code4uClient
import ai.code4u.plugin.client.Position
import ai.code4u.plugin.client.RefactorRequest
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.ui.Messages
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing

class GenerateAction : AnAction() {
    
    private val client = Code4uClient()
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val prompt = Messages.showInputDialog(
            project,
            "Describe what code you want to generate:",
            "code4u.ai - Generate Code",
            null
        )
        
        if (prompt.isNullOrBlank()) return
        
        val offset = editor.caretModel.offset
        val line = editor.document.getLineNumber(offset)
        val col = offset - editor.document.getLineStartOffset(line)
        
        val request = RefactorRequest(
            intent = "Generate: $prompt",
            file_path = file.path,
            selection_start = Position(line, col),
            selection_end = Position(line, col),
            workspace_id = project.basePath ?: "default"
        )
        
        CoroutineScope(Dispatchers.IO).launch {
            var generatedCode = ""
            
            client.executeRefactor(
                request = request,
                onEvent = { event ->
                    if (event.type == "diff" && event.diff != null) {
                        generatedCode = event.diff.modified
                    }
                },
                onComplete = {
                    launch(Dispatchers.Swing) {
                        if (generatedCode.isNotBlank()) {
                            WriteCommandAction.runWriteCommandAction(project) {
                                editor.document.setText(generatedCode)
                            }
                        }
                    }
                },
                onError = { error ->
                    launch(Dispatchers.Swing) {
                        Messages.showErrorDialog(project, error, "code4u.ai Error")
                    }
                }
            )
        }
    }
    
    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor != null
    }
}

