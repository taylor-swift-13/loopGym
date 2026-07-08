int unknown();
void foo135() {

    int p;
    int c;
    int cl;

    cl = unknown();
    p = 0;
    c = cl;


    
    while(p < 4 && cl > 0){
       cl = cl - 1;
       p = p + 1;
      }

    /*@ assert (c >= 4) ==> (p == 4); */

  }