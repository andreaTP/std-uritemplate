package org.uritemplate;

import java.util.Map;

public class UriTemplateMicronautWrapper implements UriTemplate {

    private String template = null;
    private Map<String, Object> substs = null;

    public void prepare(final String template, final Map<String, Object> substitutions) {
        this.template = template;
        this.substs = substitutions;
    }

    public String benchmark() {
        return new UriTemplateMicronaut(template).expand(substs);
    }

}
