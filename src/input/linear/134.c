int unknown();
void foo134() {

    int p;
    int c;
    int cl;

    cl = unknown();
    p = 0;
    c = cl;


    
    while(((p < 4) && (cl > 0))){
       (cl = cl - 1);
       (p = p + 1);
      }

    /*@ assert ((p != 4) ==> (c < 4)); */

  }