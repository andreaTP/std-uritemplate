package org.uritemplate;

import java.util.Map;

public interface UriTemplate {

    public void prepare(final String template, final Map<String, Object> substitutions);
    public String benchmark();
}
