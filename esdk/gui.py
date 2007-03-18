#!/usr/bin/python -tt
# vim: ai ts=4 sts=4 et sw=4

import pygtk
try:
    import gtk, gtk.glade, gobject
except:
    raise ImportError, "Unable to import the gtk libraries.  Maybe you are running in text mode"
from SDK import *

global gladefile
gladefile = "/usr/share/esdk/esdk.glade"
if not os.path.isfile(gladefile):
    raise IOError, "Glade file is missing from: %s" % gladefile

class esdkMain:
    """This is our main"""
    def __init__(self):
        self.widgets = gtk.glade.XML (gladefile, 'main')
        # FIXME: Delete or uncomment below line
        #self.widgets.signal_autoconnect(callbacks.__dict__)
        dic = {"on_main_destroy_event" : gtk.main_quit,
                "on_quit_activate" : gtk.main_quit,
                "on_newProject_clicked" : self.on_newProject_clicked,
                "on_projectDelete_clicked": self.on_projectDelete_clicked,
                "on_projectSave_clicked": self.on_projectSave_clicked,
                "on_new_target_add_clicked": self.on_new_target_add_clicked,
                "on_delete_target_clicked": self.on_delete_target_clicked,
                "on_install_fset": self.on_install_fset,
                "on_about_activate": self.on_about_activate}
        self.widgets.signal_autoconnect(dic)
        # setup projectView widget
        self.pName = "Name"
        self.pDesc = "Description"
        self.pPath = "Path"
        self.pPlatform = "Platform"
        self.projectView = self.widgets.get_widget("projectView")
        print "Setting Project List"
        self.set_plist(self.pName, 0)
        self.set_plist(self.pDesc, 1)
        self.set_plist(self.pPath, 2)
        self.set_plist(self.pPlatform, 3)
        self.projectList = gtk.ListStore(str, str, str, str)
        self.projectView.set_model(self.projectList)
        self.projectView.set_reorderable(1)
        # Set targetView widget
        self.tName = "Name"
        self.tFSet = "FSets"
        self.targetView = self.widgets.get_widget("targetView")
        print "Setting Target List"
        self.set_tlist(self.tName, 0)
        self.set_tlist(self.tFSet, 1)
        self.targetList = gtk.ListStore(str, str)
        self.targetView.set_model(self.targetList)
        # read in project list using SDK()
        for key in sorted(SDK().projects.iterkeys()):
            p = SDK().projects[key]
            self.projectList.append((p.name, p.desc, p.path, p.platform.name))
        self.buttons = MainWindowButtons(self.widgets)
        # Connect project selection signal to list targets in the targetList
        # widget: targetView
        self.projectView.get_selection().connect("changed", self.project_view_changed)
        self.targetView.get_selection().connect("changed", self.target_view_changed)

    def target_view_changed(self, selection):
        model, iter = self.targetView.get_selection().get_selected()
        if not iter:
            # No targets are selected
            self.buttons.delete_target.set_sensitive(False)
            self.buttons.install_fset.set_sensitive(False)
            return
        # A target has been selected
        self.buttons.delete_target.set_sensitive(True)
        self.buttons.install_fset.set_sensitive(True)
        
    def project_view_changed(self, selection):
        self.targetList.clear()
        model, iter = self.projectView.get_selection().get_selected()
        if not iter:
            # No projects are selected
            self.buttons.delete_project.set_sensitive(False)
            self.buttons.save_project.set_sensitive(False)
            self.buttons.add_target.set_sensitive(False)
            self.buttons.install_fset.set_sensitive(False)
            self.buttons.delete_target.set_sensitive(False)
            return
        # We have a project selected, so it makes sense for the
        # delete project and add target buttons to be sensitive
        self.buttons.delete_project.set_sensitive(True)
        self.buttons.add_target.set_sensitive(True)
        for key in self.current_project().targets:
            installed_fsets = ''
            for fset in self.current_project().targets[key].installed_fsets():
                installed_fsets = installed_fsets + fset + ' '
            self.targetList.append((key, installed_fsets))

    def set_plist(self, name, id):
        """Add project list column descriptions"""
        column = gtk.TreeViewColumn(name, gtk.CellRendererText(), text=id)
        column.set_resizable(True)
        column.set_sort_column_id(id)
        self.projectView.append_column(column)

    def set_tlist(self, name, id):
        """Add target list column descriptions"""
        column = gtk.TreeViewColumn(name, gtk.CellRendererText(), text=id)
        column.set_resizable(True)
        column.set_sort_column_id(id)
        self.targetView.append_column(column)

    def on_newProject_clicked(self, widget):
        """Instantiate a new dialogue"""
        print "New project Dialogue"
        new_project = AddNewProject();
        # Now call its run method
        result,new_project = AddNewProject.run(new_project)
        if result == gtk.RESPONSE_OK:
            # The user clicked Ok, so let's add this project to the projectView
            # list
            print "user pressed OK"
            sdk = SDK()
            platform = sdk.platforms[new_project.platform]
            print "platform %s "  % platform.name
            proj = sdk.create_project(new_project.path, new_project.name, new_project.desc, platform)
            # FIXME: finish packing this dialogue
            if proj:
                print "Project create OK"
                # FIXME: error check
                proj.install()
                self.projectList.append(new_project.getList())

    def on_about_activate(self, event):
        dialog = gtk.AboutDialog()
        dialog.set_name('Embedded Linux SDK: Project Builder')
        dialog.set_version('0.01 Pre-Alpha')
        dialog.set_comments('This is the graphical user front-end to the project-builder utility')
        dialog.set_license('TODO: Add License')
        dialog.set_website('http://umd.jf.intel.com')
        dialog.set_website_label('ESDK Developement')
        dialog.run()
        dialog.destroy()
        
    def on_projectSave_clicked(self, event):
        print "Not yet implemented"

    def on_projectDelete_clicked(self, event):
        """Delete a Project"""
        project = self.current_project()
        tree = gtk.glade.XML(gladefile, 'qDialog')
        tree.get_widget('queryLabel').set_text("Delete the %s project?" % (project.name))
        dialog = tree.get_widget('qDialog')
        if dialog.run() == gtk.RESPONSE_OK:
            SDK().delete_project(project.name)
            self.remove_current_project()
        dialog.destroy()

    def on_new_target_add_clicked(self, widget):
        # Open the "New Target" dialog
        widgets = gtk.glade.XML(gladefile, 'nt_dlg')
        dialog = widgets.get_widget('nt_dlg')
        if dialog.run() == gtk.RESPONSE_OK:
            target_name = widgets.get_widget('nt_name').get_text()
            self.current_project().create_target(target_name)
            self.targetList.append((target_name, ''))
        dialog.destroy()

    def on_install_fset(self, widget):
        tree = gtk.glade.XML(gladefile, 'installFsetDialog')
        dialog = tree.get_widget('installFsetDialog')
        list = gtk.ListStore(gobject.TYPE_STRING)            
        for fset in self.current_project().platform.fset:
            list.append([fset])
        cebox = tree.get_widget('installed_fsets')
        cebox.set_model(list)
        cebox.set_text_column(0)
        cebox.child.set_text(list[0][0])
        if dialog.run() == gtk.RESPONSE_OK:
            print "Install the fset %s" % (cebox.child.get_text())
        dialog.destroy()
        
    def on_delete_target_clicked(self, widget):
        project = self.current_project()
        target = self.current_target()
        tree = gtk.glade.XML(gladefile, 'qDialog')
        tree.get_widget('queryLabel').set_text("Delete target %s from project %s?" % (target.name, project.name))
        dialog = tree.get_widget('qDialog')
        if dialog.run() == gtk.RESPONSE_OK:
            SDK().projects[project.name].delete_target(target.name)
            self.remove_current_target()
        dialog.destroy()

    def current_project(self):
        model, iter = self.projectView.get_selection().get_selected()
        return SDK().projects[model[iter][0]]

    def current_target(self):
        model, iter = self.targetView.get_selection().get_selected()
        return self.current_project().targets[model[iter][0]]

    def remove_current_project(self):
        model, iter = self.projectView.get_selection().get_selected()
        self.projectList.remove(iter)

    def remove_current_target(self):
        model, iter = self.targetView.get_selection().get_selected()
        self.targetList.remove(iter)

class ProjectInfo:
    """Class to store new project info before we persist"""
    def __init__(self, name="", desc="", path="", platform=""):
        self.name = name
        self.desc = desc
        self.path = path
        self.platform = platform

    def getList(self):
        return (self.name, self.desc, self.path, self.platform)

class AddNewProject:
    """Class to bring up AddNewProject dialogue"""
    def __init__(self, name="", desc="", path="", platform=""):
        self.newProject = ProjectInfo(name,desc,path,platform)

    def on_newDlg_destroy(event):
        print "Destroying dialogue"
        gtk.newProject.destroy()

    def on_newDlg_cancel_clicked(event):
        print "dialogue closing"

    def run(self):
        self.widgets = gtk.glade.XML (gladefile, 'newProject')
        self.widgets.signal_autoconnect({"on_browse": self.on_browse})
        self.newDlg = self.widgets.get_widget('newProject')
        # Get all of the Entry Widgets and set their text
        self.np_name = self.widgets.get_widget("np_name")
        self.np_name.set_text(self.newProject.name)
        self.np_desc = self.widgets.get_widget("np_desc")
        self.np_desc.set_text(self.newProject.desc)
        self.np_path = self.widgets.get_widget("np_path")
        self.np_path.set_text(self.newProject.path)
        self.np_platform = self.widgets.get_widget("np_platform")
        platform_entry_box = gtk.ListStore(gobject.TYPE_STRING)
        for pname in sorted(SDK().platforms.iterkeys()):
            platform_entry_box.append([pname])
        self.np_platform.set_model(platform_entry_box)
        self.np_platform.set_text_column(0)
        self.np_platform.child.set_text(platform_entry_box[0][0])
        self.result = self.newDlg.run()
        # get the values
        self.newProject.name = self.np_name.get_text()
        self.newProject.desc = self.np_desc.get_text()
        self.newProject.path = self.np_path.get_text()
        self.newProject.platform = self.np_platform.child.get_text()
        if self.result == gtk.RESPONSE_CANCEL:
            print "User cancelled New project Add"
            self.newDlg.destroy()
        self.newDlg.destroy()
        return self.result,self.newProject

    def on_browse(self, button):
        dialog = gtk.FileChooserDialog(action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, title="Choose Project Directory")
        dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_OK)
        dialog.add_button(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL)
        if dialog.run() == gtk.RESPONSE_OK:
            self.np_path.set_text(dialog.get_current_folder())
        dialog.destroy()
        
class MainWindowButtons:
    def __init__(self, widgets):
        # Project button bar
        self.add_project = widgets.get_widget('new_project_add')
        self.delete_project = widgets.get_widget('project_delete')
        self.save_project = widgets.get_widget('project_save')
        # Target button bar
        self.add_target = widgets.get_widget('new_target_add')
        self.delete_target = widgets.get_widget('target_delete')
        self.install_fset = widgets.get_widget('target_install_fset')
        
if __name__ == '__main__':
    esdk = esdkMain()
    gtk.main()
