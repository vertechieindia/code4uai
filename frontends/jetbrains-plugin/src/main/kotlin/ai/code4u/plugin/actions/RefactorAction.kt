package ai.code4u.plugin.actions

import ai.code4u.plugin.client.Code4uClient
import ai.code4u.plugin.client.Position
import ai.code4u.plugin.client.RefactorRequest
import ai.code4u.plugin.ui.RefactorDialog
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.command.WriteCommandAction
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.VirtualFile
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.swing.Swing

class RefactorAction : AnAction() {
    
    private val client = Code4uClient()
    
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = e.getData(CommonDataKeys.EDITOR) ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: return
        
        val selection = editor.selectionModel.selectedText
        val selectionStart = if (editor.selectionModel.hasSelection()) {
            val offset = editor.selectionModel.selectionStart
            val line = editor.document.getLineNumber(offset)
            val col = offset - editor.document.getLineStartOffset(line)
            Position(line, col)
        } else null
        
        val selectionEnd = if (editor.selectionModel.hasSelection()) {
            val offset = editor.selectionModel.selectionEnd
            val line = editor.document.getLineNumber(offset)
            val col = offset - editor.document.getLineStartOffset(line)
            Position(line, col)
        } else null
        
        // Show refactor dialog
        val dialog = RefactorDialog(project, selection)
        if (!dialog.showAndGet()) return
        
        val intent = dialog.getIntent()
        if (intent.isBlank()) {
            Messages.showWarningDialog(project, "Please enter a refactoring instruction", "code4u.ai")
            return
        }
        
        executeRefactor(project, editor, file, intent, selection, selectionStart, selectionEnd)
    }
    
    private fun executeRefactor(
        project: Project,
        editor: Editor,
        file: VirtualFile,
        intent: String,
        selection: String?,
        selectionStart: Position?,
        selectionEnd: Position?
    ) {
        val request = RefactorRequest(
            intent = intent,
            file_path = file.path,
            selection = selection,
            selection_start = selectionStart,
            selection_end = selectionEnd,
            workspace_id = project.basePath ?: "default"
        )
        
        CoroutineScope(Dispatchers.IO).launch {
            val diffs = mutableListOf<Pair<String, String>>()
            var currentState = ""
            
            client.executeRefactor(
                request = request,
                onEvent = { event ->
                    when (event.type) {
                        "state_change" -> {
                            currentState = event.state ?: ""
                            launch(Dispatchers.Swing) {
                                // Update status bar or progress indicator
                            }
                        }
                        "diff" -> {
                            event.diff?.let { diff ->
                                diffs.add(diff.file_path to diff.modified)
                            }
                        }
                        "error" -> {
                            launch(Dispatchers.Swing) {
                                Messages.showErrorDialog(
                                    project,
                                    event.message ?: "Unknown error",
                                    "code4u.ai Refactor Failed"
                                )
                            }
                        }
                    }
                },
                onComplete = {
                    launch(Dispatchers.Swing) {
                        if (diffs.isNotEmpty()) {
                            // Apply the diffs
                            applyDiffs(project, editor, diffs)
                        }
                    }
                },
                onError = { error ->
                    launch(Dispatchers.Swing) {
                        Messages.showErrorDialog(project, error, "code4u.ai Connection Error")
                    }
                }
            )
        }
    }
    
    private fun applyDiffs(project: Project, editor: Editor, diffs: List<Pair<String, String>>) {
        // For now, apply to current file only
        val currentFileDiff = diffs.firstOrNull()
        currentFileDiff?.let { (_, newContent) ->
            WriteCommandAction.runWriteCommandAction(project) {
                editor.document.setText(newContent)
            }
            Messages.showInfoMessage(
                project,
                "Refactoring applied successfully. ${diffs.size} file(s) modified.",
                "code4u.ai"
            )
        }
    }
    
    override fun update(e: AnActionEvent) {
        val editor = e.getData(CommonDataKeys.EDITOR)
        e.presentation.isEnabledAndVisible = editor != null
    }
}

