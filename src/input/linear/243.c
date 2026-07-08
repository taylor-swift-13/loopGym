int unknown();
void foo243() {

    unsigned int x;
    unsigned int y;

    y = 1;


        x = unknown();

    while(unknown()){
       if(x % 3 == 1){
       x = x + 2;
       y = 0;
      }
       else{
       if(x % 3 == 2){
       x = x + 1;
       y = 0;
      }
       else{
       if(unknown()){
       x = x + 4;
       y = 1;
      }
       else{
       x = x + 5;
       y = 1;
      }
      }
      }
      }

    /*@ assert (y == 0) ==> (x % 3 == 0); */

  }