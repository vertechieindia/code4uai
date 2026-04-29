package ai.code4u.plugin.ui

import ai.code4u.plugin.settings.Code4uSettings
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.StatusBar
import com.intellij.openapi.wm.StatusBarWidget
import com.intellij.openapi.wm.StatusBarWidgetFactory
import com.intellij.util.Consumer
import java.awt.event.MouseEvent
import javax.swing.Icon

class Code4uStatusBarWidgetFactory : StatusBarWidgetFactory {
    
    override fun getId(): String = "code4u.statusBar"
    
    override fun getDisplayName(): String = "code4u.ai"
    
    override fun isAvailable(project: Project): Boolean = true
    
    override fun createWidget(project: Project): StatusBarWidget {
        return Code4uStatusBarWidget()
    }
    
    override fun disposeWidget(widget: StatusBarWidget) {}
    
    override fun canBeEnabledOn(statusBar: StatusBar): Boolean = true
}

class Code4uStatusBarWidget : StatusBarWidget, StatusBarWidget.TextPresentation {
    
    private val settings = Code4uSettings.instance
    private var statusBar: StatusBar? = null
    
    override fun ID(): String = "code4u.statusBar"
    
    override fun install(statusBar: StatusBar) {
        this.statusBar = statusBar
    }
    
    override fun dispose() {
        statusBar = null
    }
    
    override fun getPresentation(): StatusBarWidget.WidgetPresentation = this
    
    override fun getText(): String {
        val status = if (settings.autocompleteEnabled) "●" else "○"
        return "$status code4u.ai"
    }
    
    override fun getTooltipText(): String {
        val status = if (settings.autocompleteEnabled) "enabled" else "disabled"
        return "code4u.ai autocomplete is $status\nClick to toggle"
    }
    
    override fun getAlignment(): Float = 0f
    
    override fun getClickConsumer(): Consumer<MouseEvent>? = Consumer {
        settings.autocompleteEnabled = !settings.autocompleteEnabled
        settings.inlineCompletionEnabled = !settings.inlineCompletionEnabled
        statusBar?.updateWidget(ID())
    }
}

